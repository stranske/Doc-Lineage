"""M1 ingest pipeline: parse one document, segment it, emit an artifact manifest.

The output contract is ``artifact-manifest/v1`` from
``docs/contracts/schemas/artifact-manifest-v1.schema.json``. The manifest is
validated against that schema before anything is written, so a run either
produces a conforming manifest or fails loudly; it never leaves a half-valid
manifest on disk for a downstream consumer to trip over.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from doc_lineage.adapters import SegmenterResult, segment_document
from doc_lineage.identity import sha256_bytes
from doc_lineage.schema.validation import validate_contract_record

MANIFEST_SCHEMA_VERSION = "artifact-manifest/v1"
MANIFEST_SCHEMA_NAME = "artifact-manifest-v1"
SEGMENTS_SCHEMA_VERSION = "doc-lineage-segments/v1"
TOOL_NAME = "doc-lineage-ingest"
MANIFEST_FILENAME = "artifact-manifest.json"
SEGMENTS_FILENAME = "segments.json"
MAX_INGEST_BYTES = 100 * 1024 * 1024

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

    @property
    def page_count(self) -> int:
        pages = {segment.page for segment in self.segments}
        pages.update(self.pages_without_text_layer)
        return len(pages)


def segment_pages(result: SegmenterResult, *, source_sha256: str) -> tuple[Segment, ...]:
    """Split per-page text into paragraph segments with stable ids.

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
                )
            )
    return tuple(segments)


def build_manifest(
    *,
    run_id: str,
    source_path: Path,
    source_sha256: str,
    artifacts: list[dict[str, Any]],
    git_sha: str | None = None,
    created_at: str | None = None,
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
            "bytes": source_path.stat().st_size,
        },
        "artifacts": artifacts,
    }
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

    source_size = source.stat().st_size
    if source_size > MAX_INGEST_BYTES:
        raise ValueError(
            f"document exceeds ingest size limit ({source_size} > {MAX_INGEST_BYTES} bytes): {source}"
        )

    raw = source.read_bytes()
    if len(raw) > MAX_INGEST_BYTES:
        raise ValueError(
            f"document exceeds ingest size limit ({len(raw)} > {MAX_INGEST_BYTES} bytes): {source}"
        )
    source_sha256 = sha256_bytes(raw)
    effective_run_id = (run_id or f"ingest-{source_sha256[:12]}").strip()
    if not effective_run_id:
        raise ValueError("run_id must be a non-empty string")
    segmented = segment_document(source, allow_docling=allow_docling, data=raw)
    segments = segment_pages(segmented, source_sha256=source_sha256)
    if not segments:
        raise ValueError(
            f"no text segments recovered from {source} via backend {segmented.backend}; "
            "a recognition fallback is required before this document can be ingested"
        )

    destination = output_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    segments_payload = {
        "schema_version": SEGMENTS_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "backend": segmented.backend,
        "pages_without_text_layer": list(segmented.pages_without_text_layer),
        "segments": [segment.to_dict() for segment in segments],
    }
    segments_bytes = _dump(segments_payload)
    segments_path = destination / SEGMENTS_FILENAME

    artifacts = [
        {
            "artifact_id": f"{source_sha256[:16]}-segments",
            "name": SEGMENTS_FILENAME,
            "kind": "data",
            "path": SEGMENTS_FILENAME,
            "sha256": sha256_bytes(segments_bytes),
            "bytes": len(segments_bytes),
            "media_type": "application/json",
        }
    ]
    manifest = build_manifest(
        run_id=effective_run_id,
        source_path=source,
        source_sha256=source_sha256,
        artifacts=artifacts,
        git_sha=git_sha,
        created_at=created_at,
    )
    segments_path.write_bytes(segments_bytes)
    manifest_path = destination / MANIFEST_FILENAME
    manifest_path.write_bytes(_dump(manifest))

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
        pages_without_text_layer=segmented.pages_without_text_layer,
    )


def _dump(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
