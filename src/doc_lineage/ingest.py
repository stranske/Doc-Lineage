"""M1 ingest pipeline: parse one document, segment it, emit an artifact manifest.

The output contract is ``artifact-manifest/v1`` from
``docs/contracts/schemas/artifact-manifest-v1.schema.json``. The manifest is
validated against that schema before anything is written, so a run either
produces a conforming manifest or fails loudly; it never leaves a half-valid
manifest on disk for a downstream consumer to trip over.

Each segment also gets a standalone ``evidence-object/v1`` file under
``evidence/``, listed in the same manifest with ``kind: "evidence"``. That is
what makes an ingested fact attributable: the manifest says which bytes exist,
the evidence objects say which source text and which extraction method produced
them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from doc_lineage.extract.variables import VerifiedIngest

from doc_lineage.adapters import DOCLING_BACKEND, OFFLINE_BACKEND, SegmenterResult, segment_document
from doc_lineage.adapters.docling_segmenter import MAX_INGEST_BYTES, read_bounded_bytes
from doc_lineage.emit import EVIDENCE_DIRNAME, emit_evidence_object
from doc_lineage.extract.ocr import OCRBackend, default_ocr_backend
from doc_lineage.extract.pdf import recover_pdf_pages
from doc_lineage.identity import sha256_bytes
from doc_lineage.persistence import publish_exclusive, sync_directory, write_private

MANIFEST_SCHEMA_VERSION = "artifact-manifest/v1"
MANIFEST_SCHEMA_NAME = "artifact-manifest-v1"
SEGMENTS_SCHEMA_VERSION = "doc-lineage-segments/v1"
TOOL_NAME = "doc-lineage-ingest"
MANIFEST_FILENAME = "artifact-manifest.json"
SEGMENTS_FILENAME = "segments.json"
ORIGINAL_FILENAME = "source-{sha256}.bin"
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Segment:
    """One contiguous block of document text with a page pointer."""

    segment_id: str
    page: int
    order: int
    text: str
    char_count: int
    word_count: int
    method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IngestResult:
    """Everything one ingest run produced, in memory and on disk."""

    source_path: Path
    source_sha256: str
    run_id: str
    backend: str
    segments: tuple[Segment, ...]
    manifest: dict[str, Any]
    output_dir: Path
    manifest_path: Path
    segments_path: Path
    pages_without_text_layer: tuple[int, ...]
    evidence: tuple[dict[str, Any], ...] = ()
    evidence_dir: Path | None = None
    unreadable_pages: tuple[int, ...] = ()
    coverage_status: str = "complete"

    @property
    def page_count(self) -> int:
        pages = {segment.page for segment in self.segments}
        pages.update(self.pages_without_text_layer)
        return len(pages)


def segment_pages(
    result: SegmenterResult, *, source_sha256: str, page_methods: Mapping[int, str] | None = None
) -> tuple[Segment, ...]:
    """Split per-page text into paragraph segments with stable ids.

    Docling items arrive separated by blank lines; normalize whitespace only
    within each block so numbered headers remain visible to section pairing.

    The id is derived from the source digest plus the page and ordinal, so the
    same bytes always yield the same segment ids across machines and runs.
    """
    segments: list[Segment] = []
    order = 0
    for page in result.pages:
        for block in _PARAGRAPH_SPLIT.split(page.text):
            text = _WHITESPACE.sub(" ", block).strip()
            if not text:
                continue
            order += 1
            segments.append(
                Segment(
                    segment_id=f"{source_sha256[:16]}-p{page.page:04d}-s{order:04d}",
                    page=page.page,
                    order=order,
                    text=text,
                    char_count=len(text),
                    word_count=len(text.split()),
                    method=(page_methods or {}).get(page.page, evidence_method_for(result.backend)),
                )
            )
    return tuple(segments)


def evidence_method_for(backend: str) -> str:
    """Map a segmenter backend onto the contract's ``method`` enum.

    The enum value has to describe how the text was actually recovered, so a
    Docling parse and a plain content-stream read are not the same method.
    """
    return "parser" if backend == DOCLING_BACKEND else "text"


def build_evidence_objects(
    segments: Sequence[Segment], *, source_id: str, backend: str
) -> tuple[dict[str, Any], ...]:
    """Emit one validated ``evidence-object/v1`` per segment."""
    return tuple(
        emit_evidence_object(
            segment, source_id=source_id, method=segment.method or evidence_method_for(backend)
        )
        for segment in segments
    )


def build_manifest(
    *,
    run_id: str,
    source_path: Path,
    source_sha256: str,
    artifacts: list[dict[str, Any]],
    git_sha: str | None = None,
    created_at: str | None = None,
    source_bytes: int | None = None,
) -> dict[str, Any]:
    """Assemble an ``artifact-manifest/v1`` payload for one ingest run."""
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "tool": TOOL_NAME,
        "git_sha": git_sha,
        "created_at": created_at or datetime.now(tz=UTC).isoformat(),
        "source": {
            "filename": source_path.name,
            "sha256": source_sha256,
            "bytes": source_bytes if source_bytes is not None else source_path.stat().st_size,
        },
        "artifacts": artifacts,
    }
    from doc_lineage.schema.validation import validate_contract_record

    validate_contract_record(MANIFEST_SCHEMA_NAME, manifest)
    return manifest


def ingest_document(
    path: Path,
    *,
    output_dir: Path,
    run_id: str | None = None,
    git_sha: str | None = None,
    created_at: str | None = None,
    allow_docling: bool = True,
    ocr_enabled: bool = True,
    ocr_backend: OCRBackend | None = None,
) -> IngestResult:
    """Parse, segment, and manifest one document into ``output_dir``.

    Raises ``FileNotFoundError`` when ``path`` is missing and ``ValueError``
    when the document yields no segments, because an empty manifest cannot
    satisfy the contract's ``minItems: 1`` and an empty result is a finding,
    not a success.
    """
    source = path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"document to ingest does not exist: {source}")

    raw = read_bounded_bytes(source, MAX_INGEST_BYTES)
    source_sha256 = sha256_bytes(raw)
    effective_run_id = (run_id or f"ingest-{source_sha256[:12]}").strip()
    if not effective_run_id:
        raise ValueError("run_id must be a non-empty string")
    segmented = segment_document(source, allow_docling=allow_docling, data=raw)
    pages_without_text_layer = segmented.pages_without_text_layer
    page_methods: dict[int, str] = {}
    if pages_without_text_layer and ocr_enabled and raw.startswith(b"%PDF"):
        backend = ocr_backend if ocr_backend is not None else default_ocr_backend()
        if backend is not None:
            recovered = {
                span.page: span
                for span in recover_pdf_pages(
                    raw,
                    pages_without_text_layer,
                    ocr_backend=backend,
                    # The offline parser already tried font-aware extraction.
                    # Rejected text must only be recovered through recognition.
                    use_text_layer=segmented.backend != OFFLINE_BACKEND,
                )
            }
            segmented = replace(
                segmented,
                pages=tuple(
                    (
                        replace(page, text=recovered[page.page].text)
                        if page.page in recovered
                        else page
                    )
                    for page in segmented.pages
                ),
            )
            page_methods = {
                page: "ocr" if span.source == "ocr" else "text" for page, span in recovered.items()
            }
    segments = segment_pages(segmented, source_sha256=source_sha256, page_methods=page_methods)
    unreadable_pages = tuple(page.page for page in segmented.pages if not page.text.strip())
    coverage_status = "partial" if unreadable_pages else "complete"
    recognized_pages = {segment.page for segment in segments if segment.method == "ocr"}
    coverage = {
        "status": coverage_status,
        "pages_total": len(segmented.pages),
        "pages_with_text_layer": len(segmented.pages)
        - len(unreadable_pages)
        - len(recognized_pages),
        "pages_recognized": len(recognized_pages),
        "pages_unreadable": len(unreadable_pages),
    }
    if not segments:
        raise ValueError(
            f"no text segments recovered from {source} via backend {segmented.backend}; "
            "a recognition fallback is required before this document can be ingested"
        )

    destination = output_dir.expanduser().resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.chmod(0o700)

    segments_payload = {
        "schema_version": SEGMENTS_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "backend": segmented.backend,
        "pages_without_text_layer": list(pages_without_text_layer),
        "unreadable_pages": list(unreadable_pages),
        "coverage": coverage,
        "segments": [segment.to_dict() for segment in segments],
    }
    segments_bytes = _dump(segments_payload)
    segments_path = destination / SEGMENTS_FILENAME

    evidence_objects = build_evidence_objects(
        segments, source_id=source_sha256, backend=segmented.backend
    )
    evidence_dir = destination / EVIDENCE_DIRNAME
    evidence_files = [
        (f"{EVIDENCE_DIRNAME}/{evidence['evidence_id']}.json", _dump(evidence))
        for evidence in evidence_objects
    ]

    artifacts = [
        {
            "artifact_id": f"{source_sha256}-original",
            "name": ORIGINAL_FILENAME.format(sha256=source_sha256),
            "kind": "data",
            "path": ORIGINAL_FILENAME.format(sha256=source_sha256),
            "sha256": source_sha256,
            "bytes": len(raw),
            "media_type": "application/octet-stream",
        },
        {
            "artifact_id": f"{source_sha256[:16]}-segments",
            "name": SEGMENTS_FILENAME,
            "kind": "data",
            "path": SEGMENTS_FILENAME,
            "sha256": sha256_bytes(segments_bytes),
            "bytes": len(segments_bytes),
            "media_type": "application/json",
        },
    ]
    artifacts.extend(
        {
            "artifact_id": f"{Path(relative_path).stem}-evidence",
            "name": Path(relative_path).name,
            "kind": "evidence",
            "path": relative_path,
            "sha256": sha256_bytes(payload_bytes),
            "bytes": len(payload_bytes),
            "media_type": "application/json",
        }
        for relative_path, payload_bytes in evidence_files
    )
    manifest = build_manifest(
        run_id=effective_run_id,
        source_path=source,
        source_sha256=source_sha256,
        artifacts=artifacts,
        git_sha=git_sha,
        created_at=created_at,
        source_bytes=len(raw),
    )
    if evidence_dir.is_symlink():
        raise ValueError("evidence output directory must not be a symlink")
    original_path = destination / ORIGINAL_FILENAME.format(sha256=source_sha256)
    if original_path.is_symlink():
        raise ValueError("original snapshot must not be a symlink")
    if original_path.exists() and original_path.read_bytes() != raw:
        raise ValueError("original snapshot is immutable; use a new ingest run directory")
    if not original_path.exists():
        publish_exclusive(original_path, raw, prefix=".snapshot-")
    original_path.chmod(0o600)
    # Reused runs retain previous originals; tighten their permissions too.
    for previous_original in destination.glob("source-*.bin"):
        if (
            re.fullmatch(r"source-[0-9a-f]{64}\.bin", previous_original.name)
            and not previous_original.is_symlink()
        ):
            previous_original.chmod(0o600)
    # Also establish durability when retrying after a directory-sync failure.
    sync_directory(destination)
    evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    evidence_dir.chmod(0o700)
    write_private(segments_path, segments_bytes)
    for relative_path, payload_bytes in evidence_files:
        evidence_path = destination / relative_path
        if evidence_path.is_symlink():
            evidence_path.unlink()
        write_private(evidence_path, payload_bytes)
    # A reused run directory must not retain evidence from a previous source.
    # Only prune after the current evidence has been validated and written.
    current_evidence_names = {Path(relative_path).name for relative_path, _ in evidence_files}
    for previous_evidence in evidence_dir.glob("*.json"):
        if previous_evidence.name not in current_evidence_names:
            previous_evidence.unlink()
    manifest_path = destination / MANIFEST_FILENAME
    write_private(manifest_path, _dump(manifest))

    return IngestResult(
        source_path=source,
        source_sha256=source_sha256,
        run_id=str(manifest["run_id"]),
        backend=segmented.backend,
        segments=segments,
        manifest=manifest,
        output_dir=destination,
        manifest_path=manifest_path,
        segments_path=segments_path,
        pages_without_text_layer=pages_without_text_layer,
        unreadable_pages=unreadable_pages,
        coverage_status=coverage_status,
        evidence=evidence_objects,
        evidence_dir=evidence_dir,
    )


def _dump(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


# Full-section grammars deliberately reject qualifications, ranges and exceptions.
_RATE = r"([0-9]{1,2}(?:\.[0-9]{1,4})?|100(?:\.0{1,4})?)"
_FEE = re.compile(
    r"(?:[1-9][0-9]*\. MANAGEMENT FEE )?"
    r"The Partnership shall pay the General Partner an annual management fee equal to "
    + _RATE
    + r"% of aggregate Capital Commitments"
    r"(?: during the Commitment Period, and " + _RATE + r"% of invested capital thereafter)?\.",
    re.IGNORECASE,
)
_LPA_TITLE = re.compile(
    r"(?:SYNTHETIC )?LIMITED PARTNERSHIP AGREEMENT " r"(?:[A-Z][A-Za-z0-9'-]*[ ,]+){1,12}L\.P\."
)


def extract_variables(ingest_dir: Path, *, source: Path, entity_ref: str) -> dict[str, Any]:
    """Extract the documented management-rate subset from a verified persisted run.

    ``entity_ref`` is supplied by the caller's identity authority, never inferred
    from a PDF name. Unresolved diagnostics are separate from asserted records.
    """
    from doc_lineage.extract.variables import load_ingest

    return _extract_verified(load_ingest(ingest_dir, source), entity_ref=entity_ref)


def _extract_verified(verified: VerifiedIngest, *, entity_ref: str) -> dict[str, Any]:
    from doc_lineage.extract.variables import dump_json, validate, validate_entity
    from doc_lineage.vocab import load_legal_clauses

    validate_entity(entity_ref)
    key = load_legal_clauses()["clauses"]["legal.fees.management_rate"]["ontology_key"]
    run_id = (
        "extract-"
        + sha256_bytes(
            dump_json(
                {"source": verified.digest, "entity_ref": entity_ref, "grammar": "management-v1"}
            )
        )[:24]
    )
    candidates = [
        (segment, evidence, clause)
        for segment, evidence in zip(verified.segments, verified.evidence, strict=True)
        # Offline PDF ingest can combine a whole page. Only numbered uppercase
        # headings delimit sections; sentence punctuation and decimals do not.
        for clause in re.split(r" (?=[1-9][0-9]*\. [A-Z][A-Z ]{2,}(?: |$))", segment.text)
        if re.search(r"\bmanagement\s+fees?\b", clause, re.IGNORECASE)
    ]
    records: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    reason = None
    if not verified.complete:
        reason = "incomplete_ingest_coverage"
    elif not candidates:
        reason = "no_supported_management_fee_clause"
    elif len(candidates) != 1:
        reason = "multiple_management_fee_candidates"
    else:
        segment, evidence, clause = candidates[0]
        match = _FEE.fullmatch(clause)
        prefix = segment.text[: segment.text.index(clause)].strip()
        # Do not assert a value whose complete quotation cannot fit in evidence.
        if (
            match is None
            or evidence["excerpt"] != segment.text
            or (prefix and _LPA_TITLE.fullmatch(prefix) is None)
        ):
            reason = "unsupported_management_fee_clause"
        else:
            schedule = []
            for token, basis, period in (
                (
                    match.group(1),
                    "aggregate Capital Commitments",
                    "Commitment Period" if match.group(2) else "all",
                ),
                (match.group(2), "invested capital", "thereafter"),
            ):
                if token is not None:
                    rate = float(token)
                    schedule.append({"rate": rate, "basis": basis, "period": period})
            variable_id = "var:" + sha256_bytes(
                dump_json(
                    {
                        "source": verified.digest,
                        "entity_ref": entity_ref,
                        "key": key,
                        "segment": segment.segment_id,
                    }
                )
            )
            record = {
                "schema_version": "tracked-variable/v1",
                "variable_id": variable_id,
                "document_id": f"document:{verified.digest}",
                "artifact_id": f"{verified.digest[:16]}-segments",
                "ontology_key": key,
                "ontology_family": "clause",
                "entity_ref": entity_ref,
                "status": "asserted",
                "value_text": clause,
                "value_structured": {"unit": "percent_per_annum", "schedule": schedule},
                "evidence": evidence,
                "evidence_ref": f"evidence/{evidence['evidence_id']}.json",
                "provenance": {
                    "document": {"source_id": verified.digest, "locator": evidence["locator"]},
                    "mirror": {
                        "mirror_root": ".",
                        "blob_path": f"source/{verified.source_name}",
                        "page_anchor": f"#page={segment.page}",
                    },
                },
                "extractor_run_id": run_id,
            }
            validate("evidence-object-v1", evidence)
            validate("tracked-variable-v1", record)
            records.append(record)
    if reason:
        unresolved.append(
            {
                "ontology_key": key,
                "status": "unresolved",
                "reason": reason,
                "source_id": verified.digest,
                "evidence_refs": sorted(
                    {f"evidence/{e['evidence_id']}.json" for _, e, _ in candidates}
                ),
            }
        )
    return {"run_id": run_id, "records": records, "unresolved": unresolved}
