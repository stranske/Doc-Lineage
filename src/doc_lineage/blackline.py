"""Section-ID blackline pairing over flat ingest segments (B2-005)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from doc_lineage.ingest import Segment

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
            left_conf = _finite_confidence(left.header_confidence if left is not None else 1.0)
            right_conf = _finite_confidence(right.header_confidence if right is not None else 1.0)
            confidence = min(left_conf, right_conf)
            if (
                left is None
                or right is None
                or duplicate_ambiguity
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
    directory.mkdir(parents=True, exist_ok=True)
    # Exclusive creation never replaces an earlier record, even on an ID collision.
    with (directory / f"{record['comparison_id']}.json").open("x", encoding="utf-8") as output:
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
