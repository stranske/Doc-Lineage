"""Section-ID blackline pairing over flat ingest segments (B2-005)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import zlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from jsonschema import ValidationError

from doc_lineage.identity import sha256_bytes
from doc_lineage.ingest import (
    MANIFEST_FILENAME,
    ORIGINAL_FILENAME,
    SEGMENTS_FILENAME,
    SEGMENTS_SCHEMA_VERSION,
    Segment,
)
from doc_lineage.persistence import publish_exclusive
from doc_lineage.schema.validation import validate_contract_record

LINEAGE_EDGES_SCHEMA_VERSION = "lineage-edges/v1"
DEFAULT_HEADER_CONFIDENCE_THRESHOLD = 0.8
SECTION_HEADER_RE = re.compile(r"^(\d+)\.\s+((?:[A-Z]{2,}(?:\s+[A-Z]{2,})*))(?:\s+(.*))?$")
PairingMethod = Literal["section_id", "manual_review"]
MANUAL_REVIEW_CONFIDENCE = 0.0


@dataclass(frozen=True)
class Section:
    section_id: str
    title: str
    header_confidence: float
    segment_ids: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class DocumentSections:
    source_sha256: str
    sections: tuple[Section, ...]


@dataclass(frozen=True)
class SectionPair:
    section_id: str
    left: Section | None
    right: Section | None
    pairing_method: PairingMethod
    confidence: float


def _finite_confidence(value: float) -> float:
    """Map non-finite header confidence to a safe manual-review floor."""
    if not math.isfinite(value):
        return MANUAL_REVIEW_CONFIDENCE
    return value


def _parse_section_header(text: str) -> tuple[str, str, float] | None:
    match = SECTION_HEADER_RE.match(text.strip())
    if not match:
        return None
    section_id, title = match.group(1), match.group(2).strip()
    if not title:
        return None
    return section_id, title, 1.0


def build_section_tree(
    segments: Sequence[Segment],
    *,
    source_sha256: str,
) -> DocumentSections:
    """Group flat ingest segments into numbered sections by header IDs."""
    sections: list[Section] = []
    current_id: str | None = None
    current_title = ""
    current_confidence = 0.0
    current_segment_ids: list[str] = []
    current_text_parts: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_title, current_confidence
        nonlocal current_segment_ids, current_text_parts
        if current_id is None or not current_segment_ids:
            current_id = None
            current_title = ""
            current_confidence = 0.0
            current_segment_ids = []
            current_text_parts = []
            return
        sections.append(
            Section(
                section_id=current_id,
                title=current_title,
                header_confidence=current_confidence,
                segment_ids=tuple(current_segment_ids),
                text="\n".join(current_text_parts),
            )
        )
        current_id = None
        current_title = ""
        current_confidence = 0.0
        current_segment_ids = []
        current_text_parts = []

    for segment in segments:
        parsed = _parse_section_header(segment.text)
        if parsed is not None:
            flush()
            current_id, current_title, current_confidence = parsed
            current_segment_ids = [segment.segment_id]
            current_text_parts = [segment.text]
            continue
        if current_id is None:
            continue
        current_segment_ids.append(segment.segment_id)
        current_text_parts.append(segment.text)

    flush()
    return DocumentSections(source_sha256=source_sha256, sections=tuple(sections))


def _sections_by_id(sections: Sequence[Section]) -> dict[str, list[Section]]:
    grouped: dict[str, list[Section]] = {}
    for section in sections:
        grouped.setdefault(section.section_id, []).append(section)
    return grouped


def align_sections(
    doc_a: DocumentSections,
    doc_b: DocumentSections,
    *,
    threshold: float = DEFAULT_HEADER_CONFIDENCE_THRESHOLD,
) -> list[SectionPair]:
    """Pair sections by stable section IDs before any semantic fallback."""
    effective_threshold = threshold if math.isfinite(threshold) else float("inf")
    left_groups = _sections_by_id(doc_a.sections)
    right_groups = _sections_by_id(doc_b.sections)
    ordered_ids = sorted(
        set(left_groups) | set(right_groups),
        key=lambda value: int(value),
    )
    pairs: list[SectionPair] = []

    for section_id in ordered_ids:
        left_list = left_groups.get(section_id, [])
        right_list = right_groups.get(section_id, [])
        duplicate_ambiguity = len(left_list) > 1 or len(right_list) > 1
        pair_count = max(len(left_list), len(right_list), 1)

        for index in range(pair_count):
            left = left_list[index] if index < len(left_list) else None
            right = right_list[index] if index < len(right_list) else None
            left_conf = left.header_confidence if left is not None else 1.0
            right_conf = right.header_confidence if right is not None else 1.0
            confidence = min(_finite_confidence(left_conf), _finite_confidence(right_conf))
            if (
                left is None
                or right is None
                or duplicate_ambiguity
                # Sanitizing for serialization must not make invalid confidence
                # eligible for automatic pairing at a zero threshold.
                or not math.isfinite(left_conf)
                or not math.isfinite(right_conf)
                or confidence < effective_threshold
            ):
                pairing_method: PairingMethod = "manual_review"
            else:
                pairing_method = "section_id"
            pairs.append(
                SectionPair(
                    section_id=section_id,
                    left=left,
                    right=right,
                    pairing_method=pairing_method,
                    confidence=confidence,
                )
            )
    return pairs


def lineage_edge_for(pair: SectionPair) -> dict[str, Any]:
    """Serialize one pairing decision as a lineage-edges/v1 record."""
    confidence = _finite_confidence(pair.confidence)
    return {
        "schema_version": LINEAGE_EDGES_SCHEMA_VERSION,
        "section_id": pair.section_id,
        "left_section_id": pair.left.section_id if pair.left is not None else None,
        "right_section_id": pair.right.section_id if pair.right is not None else None,
        "pairing_method": pair.pairing_method,
        "confidence": confidence,
        "left_title": pair.left.title if pair.left is not None else None,
        "right_title": pair.right.title if pair.right is not None else None,
    }


def emit_lineage_edges_ndjson(pairs: Iterable[SectionPair]) -> str:
    """Render aligned pairs as newline-delimited lineage edge records."""
    return "\n".join(json.dumps(lineage_edge_for(pair), sort_keys=True) for pair in pairs)


# Repo-owned envelope: same opaque ID syntax as the independently developed
# DOCX scope (#110 / PR #127), with a separate schema and explicit fidelity mode.
SECTION_COMPARISON_SCHEMA = "section-pairing-comparison/v1"
SECTION_COMPARISON_ID_RE = re.compile(r"cmp_[0-9a-f]{32}")
SECTION_PAIRING_MODE = "extracted-pdf-sections"


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def _json_object(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("expected object")
        _canonical_bytes(value)
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"invalid {description}") from exc
    return value


def _run_file(run: Path, relative: str) -> bytes:
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or "\\" in relative
        or ":" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or any((run / Path(*path.parts[:i])).is_symlink() for i in range(1, len(path.parts) + 1))
    ):
        raise ValueError("unsafe ingest artifact path")
    try:
        return (run / relative).read_bytes()
    except OSError as exc:
        raise ValueError(f"missing or unreadable ingest artifact: {relative}") from exc


def load_section_ingest(run_dir: Path) -> tuple[dict[str, str], DocumentSections]:
    """Validate a persisted PDF ingest, including every manifested artifact.

    No parsing, OCR, network or native helper runs here. Legacy runs without a
    retained original must be ingested again into a new directory.
    """
    run = run_dir.expanduser().resolve()
    manifest_bytes = _run_file(run, MANIFEST_FILENAME)
    manifest = _json_object(manifest_bytes, "ingest manifest")
    try:
        validate_contract_record("artifact-manifest-v1", manifest)
    except (ValueError, ValidationError) as exc:
        raise ValueError("invalid ingest manifest") from exc
    if manifest.get("tool") != "doc-lineage-ingest":
        raise ValueError("not a doc-lineage ingest manifest")
    source = manifest.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("sha256"), str):
        raise ValueError("missing original source binding")
    digest = source["sha256"]
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid original source digest")
    artifacts: dict[str, bytes] = {}
    ids: set[str] = set()
    for artifact in manifest["artifacts"]:
        relative = artifact["path"]
        if relative in artifacts or artifact["artifact_id"] in ids:
            raise ValueError("duplicate ingest artifact binding")
        raw = _run_file(run, relative)
        if sha256_bytes(raw) != artifact["sha256"] or len(raw) != artifact.get("bytes"):
            raise ValueError(f"ingest artifact hash/size mismatch: {relative}")
        artifacts[relative] = raw
        ids.add(artifact["artifact_id"])
    original_name = ORIGINAL_FILENAME.format(sha256=digest)
    if original_name not in artifacts:
        raise ValueError("missing retained original source; re-ingest into a new run directory")
    original = artifacts[original_name]
    if sha256_bytes(original) != digest or len(original) != source.get("bytes"):
        raise ValueError("original source binding mismatch")
    if not original.startswith(b"%PDF-"):
        raise ValueError("section pairing requires PDF ingests; native DOCX is a separate mode")
    if SEGMENTS_FILENAME not in artifacts:
        raise ValueError("missing segments artifact binding")
    segment_bytes = artifacts[SEGMENTS_FILENAME]
    payload = _json_object(segment_bytes, "segments payload")
    if (
        payload.get("schema_version") != SEGMENTS_SCHEMA_VERSION
        or payload.get("source_sha256") != digest
    ):
        raise ValueError("segments source/schema binding mismatch")
    rows = payload.get("segments")
    if not isinstance(rows, list) or not rows:
        raise ValueError("invalid empty segments payload")
    segments: list[Segment] = []
    last_page = 1
    for order, row in enumerate(rows, start=1):
        try:
            segment = Segment(**row)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid segment record") from exc
        if (
            type(segment.page) is not int
            or segment.page < last_page
            or type(segment.order) is not int
            or segment.order != order
            or segment.segment_id != f"{digest[:16]}-p{segment.page:04d}-s{order:04d}"
            or not isinstance(segment.text, str)
            or not segment.text.strip()
            or segment.char_count != len(segment.text)
            or segment.word_count != len(segment.text.split())
            or segment.method not in {"text", "parser", "ocr", None}
        ):
            raise ValueError("invalid segment content/order binding")
        last_page = segment.page
        segments.append(segment)
    binding = {
        "source_sha256": digest,
        "segments_sha256": sha256_bytes(segment_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
    }
    return binding, build_section_tree(segments, source_sha256=digest)


def _section_comparison(
    original_run: Path, modified_run: Path, threshold: float
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if isinstance(threshold, bool) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and between 0 and 1")
    original, left = load_section_ingest(original_run)
    modified, right = load_section_ingest(modified_run)
    identity = {
        "schema_version": "comparison-identity/v1",
        "mode": SECTION_PAIRING_MODE,
        "original": original,
        "modified": modified,
        "options": {"header_confidence_threshold": float(threshold), "engine": "section-id/v1"},
    }
    decisions = [
        lineage_edge_for(pair) for pair in align_sections(left, right, threshold=threshold)
    ]
    return identity, decisions


def create_section_comparison(
    original_run: Path,
    modified_run: Path,
    *,
    store: Path,
    threshold: float = DEFAULT_HEADER_CONFIDENCE_THRESHOLD,
) -> str:
    """Publish an immutable section-pair artifact after validating both inputs."""
    identity, decisions = _section_comparison(original_run, modified_run, threshold)
    directory = store.expanduser().resolve()
    record = {
        "schema_version": SECTION_COMPARISON_SCHEMA,
        "comparison_id": f"cmp_{uuid4().hex}",
        "identity": identity,
        "identity_sha256": sha256_bytes(_canonical_bytes(identity)),
        # Relative locators allow moving the complete local bundle together.
        "runs": {
            "original": os.path.relpath(original_run.expanduser().resolve(), directory),
            "modified": os.path.relpath(modified_run.expanduser().resolve(), directory),
        },
        "decisions": decisions,
    }
    record["record_sha256"] = sha256_bytes(_canonical_bytes(record))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    publish_exclusive(
        directory / f"{record['comparison_id']}.json",
        _canonical_bytes(record),
        prefix=".section-",
    )
    return str(record["comparison_id"])


def load_section_comparison(
    comparison_id: str,
    *,
    store: Path,
    original_run: Path | None = None,
    modified_run: Path | None = None,
    threshold: float | None = None,
) -> dict[str, Any]:
    """Lookup and replay from persisted bytes; return nothing until validated.

    Optional input arguments assert the caller's intended source order/options.
    Hashes detect corruption, not a malicious actor rewriting all local records.
    """
    if SECTION_COMPARISON_ID_RE.fullmatch(comparison_id) is None:
        raise ValueError("not a comparison ID; expected cmp_<32 lowercase hex>, never a path")
    directory = store.expanduser().resolve()
    target = directory / f"{comparison_id}.json"
    if target.is_symlink():
        raise ValueError("comparison artifact must not be a symlink")
    try:
        raw = target.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"unknown comparison ID: {comparison_id}") from exc
    record = _json_object(raw, "comparison artifact")
    checksum = record.pop("record_sha256", None)
    if checksum != sha256_bytes(_canonical_bytes(record)):
        raise ValueError("comparison artifact tamper: record hash mismatch")
    record["record_sha256"] = checksum
    try:
        if (
            record["schema_version"] != SECTION_COMPARISON_SCHEMA
            or record["comparison_id"] != comparison_id
        ):
            raise ValueError("comparison schema/mode/ID mismatch")
        identity = record["identity"]
        if not isinstance(identity, dict) or identity.get("mode") != SECTION_PAIRING_MODE:
            raise ValueError("comparison schema/mode/ID mismatch")
        recorded_threshold = identity["options"]["header_confidence_threshold"]
        if threshold is not None and threshold != recorded_threshold:
            raise ValueError("pairing options mismatch")
        if (original_run is None) != (modified_run is None):
            raise ValueError("provide both ordered ingest runs or neither")
        runs = record["runs"]
        if any(
            not isinstance(runs[role], str) or not runs[role] for role in ("original", "modified")
        ):
            raise ValueError("invalid ingest run locators")
        left = original_run if original_run is not None else directory / runs["original"]
        right = modified_run if modified_run is not None else directory / runs["modified"]
        current_identity, decisions = _section_comparison(left, right, recorded_threshold)
        if (
            current_identity["original"] == identity["modified"]
            and current_identity["modified"] == identity["original"]
            and identity["original"] != identity["modified"]
        ):
            raise ValueError("source order mismatch")
        if (
            current_identity != identity
            or sha256_bytes(_canonical_bytes(identity)) != record["identity_sha256"]
        ):
            raise ValueError("comparison input tamper: source/segments/manifest/options mismatch")
        if decisions != record["decisions"]:
            raise ValueError("comparison decisions tamper or unsupported engine version")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("invalid comparison artifact structure") from exc
    return record


COMPARISON_SCHEMA_VERSION = "docx-comparison/v1"
COMPARISON_ID_RE = re.compile(r"cmp_[0-9a-f]{32}")


@dataclass(frozen=True)
class ComparisonRecord:
    comparison_id: str
    original_path: Path
    modified_path: Path
    original_sha256: str
    modified_sha256: str


def comparison_store_path(store: Path | None = None) -> Path:
    """Local records are independent of the invoking process's working directory."""
    return store if store is not None else Path.home() / ".doc-lineage" / "comparisons"


def _validate_docx(content: bytes, path: Path) -> None:
    try:
        with ZipFile(BytesIO(content)) as package:
            if not {"[Content_Types].xml", "word/document.xml"} <= set(package.namelist()):
                raise ValueError(f"Not a DOCX package: {path}")
            if package.testzip() is not None:
                raise ValueError(f"Corrupt DOCX package: {path}")
    except BadZipFile as exc:
        raise ValueError(f"Not a DOCX package: {path}") from exc
    except (zlib.error, EOFError, NotImplementedError, RuntimeError) as exc:
        raise ValueError(f"Corrupt DOCX package: {path}") from exc


def write_comparison_record(original: Path, modified: Path, *, store: Path | None = None) -> str:
    """Bind ordered DOCX inputs to their exact bytes without modifying sources."""
    record = {"schema_version": COMPARISON_SCHEMA_VERSION, "comparison_id": f"cmp_{uuid4().hex}"}
    for role, source in (("original", original), ("modified", modified)):
        path = source.resolve(strict=True)
        content = path.read_bytes()
        _validate_docx(content, path)
        record[f"{role}_path"] = str(path)
        record[f"{role}_sha256"] = hashlib.sha256(content).hexdigest()
    directory = comparison_store_path(store)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Exclusive creation never replaces an earlier record, even on an ID collision.
    target = directory / f"{record['comparison_id']}.json"
    descriptor = os.open(
        target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record["comparison_id"]


def load_comparison_record(comparison_id: str, *, store: Path | None = None) -> ComparisonRecord:
    """Resolve an opaque ID only; a path is never interpreted as a record location."""
    if COMPARISON_ID_RE.fullmatch(comparison_id) is None:
        raise ValueError(f"Not a comparison ID: {comparison_id!r}; expected cmp_<32 lowercase hex>")
    path = comparison_store_path(store) / f"{comparison_id}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Unknown comparison ID: {comparison_id}") from exc
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid comparison record: {comparison_id}") from exc
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != COMPARISON_SCHEMA_VERSION
        or record.get("comparison_id") != comparison_id
        or any(
            not isinstance(record.get(f"{role}_path"), str)
            or not Path(record[f"{role}_path"]).is_absolute()
            or not isinstance(record.get(f"{role}_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", record[f"{role}_sha256"]) is None
            for role in ("original", "modified")
        )
    ):
        raise ValueError(f"Invalid comparison record: {comparison_id}")
    return ComparisonRecord(
        comparison_id=comparison_id,
        original_path=Path(record["original_path"]),
        modified_path=Path(record["modified_path"]),
        original_sha256=record["original_sha256"],
        modified_sha256=record["modified_sha256"],
    )
