"""Incremental manifest generation over a document library tree."""

from __future__ import annotations

import json
import mimetypes
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from doc_lineage.identity import (
    DocumentIdentity,
    compute_identity,
    normalized_supersession_group,
    parse_numeric_prefix,
)

TEXT_LAYER_VALUES = frozenset({"present", "absent", "unknown"})
DOCUMENT_SUFFIXES = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".html",
    ".htm",
}


@dataclass(frozen=True)
class ManifestRow:
    stable_id: str
    sha256: str
    path: str
    entity_slug: str
    category: str
    as_of: str
    received_at: str
    bytes: int
    mime: str
    supersedes: str | None
    text_layer: str
    supersession_evidence: str | None = None

    def to_json(self) -> str:
        payload = asdict(self)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _received_at(path: Path) -> str:
    timestamp = path.stat().st_mtime
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _guess_mime(path: Path) -> str:
    mime, _encoding = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _iter_documents(root: Path) -> list[Path]:
    documents: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in DOCUMENT_SUFFIXES:
            continue
        documents.append(path)
    return documents


def _assign_supersedes(rows: list[ManifestRow]) -> list[ManifestRow]:
    by_directory: dict[Path, list[tuple[ManifestRow, int | None, str | None]]] = defaultdict(list)
    for row in rows:
        path = Path(row.path)
        prefix, _rest, convention = parse_numeric_prefix(path.name)
        by_directory[path.parent].append((row, prefix, convention))

    superseded_by: dict[str, str] = {}
    evidence_by_target: dict[str, str] = {}
    for directory_rows in by_directory.values():
        groups: dict[str, list[tuple[ManifestRow, int | None, str | None]]] = defaultdict(list)
        for row, prefix, convention in directory_rows:
            groups[normalized_supersession_group(row.path)].append((row, prefix, convention))
        for group in groups.values():
            numbered = [
                (row, prefix, convention) for row, prefix, convention in group if prefix is not None
            ]
            if len(numbered) < 2:
                continue
            numbered.sort(key=lambda item: item[1] or 0)
            for idx in range(1, len(numbered)):
                older_row, _older_prefix, _older_conv = numbered[idx - 1]
                newer_row, _newer_prefix, newer_conv = numbered[idx]
                superseded_by[newer_row.stable_id] = older_row.stable_id
                if newer_conv:
                    evidence_by_target[newer_row.stable_id] = newer_conv

    updated: list[ManifestRow] = []
    for row in rows:
        supersedes = superseded_by.get(row.stable_id)
        evidence = evidence_by_target.get(row.stable_id)
        updated.append(
            ManifestRow(
                stable_id=row.stable_id,
                sha256=row.sha256,
                path=row.path,
                entity_slug=row.entity_slug,
                category=row.category,
                as_of=row.as_of,
                received_at=row.received_at,
                bytes=row.bytes,
                mime=row.mime,
                supersedes=supersedes,
                text_layer=row.text_layer,
                supersession_evidence=evidence,
            )
        )
    return updated


def build_manifest_rows(root: Path) -> list[ManifestRow]:
    """Scan ``root`` and return sorted manifest rows."""
    root = root.resolve()
    rows: list[ManifestRow] = []
    for file_path in _iter_documents(root):
        identity = compute_identity(root, file_path)
        relative_path = file_path.relative_to(root).as_posix()
        rows.append(
            ManifestRow(
                stable_id=identity.stable_id,
                sha256=identity.sha256,
                path=relative_path,
                entity_slug=identity.entity_slug,
                category=identity.category,
                as_of=identity.as_of,
                received_at=_received_at(file_path),
                bytes=file_path.stat().st_size,
                mime=_guess_mime(file_path),
                supersedes=None,
                text_layer="unknown",
            )
        )
    rows = _assign_supersedes(rows)
    return sorted(rows, key=lambda row: row.path)


def read_manifest(path: Path) -> dict[str, str]:
    """Return existing manifest lines keyed by path."""
    if not path.exists():
        return {}
    lines: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload: dict[str, Any] = json.loads(line)
        lines[str(payload["path"])] = line
    return lines


def write_manifest(root: Path, output_path: Path) -> None:
    """Write an incremental manifest, preserving unchanged rows byte-for-byte."""
    rows = build_manifest_rows(root)
    previous_lines = read_manifest(output_path)
    output_lines: list[str] = []
    for row in rows:
        serialized = row.to_json()
        previous = previous_lines.get(row.path)
        if previous is not None:
            previous_payload = json.loads(previous)
            current_payload = json.loads(serialized)
            if previous_payload == current_payload:
                serialized = previous
        output_lines.append(serialized)

    content = "\n".join(output_lines)
    if output_lines:
        content += "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def identity_for_path(root: Path, file_path: Path) -> DocumentIdentity:
    """Expose identity computation for tests and callers."""
    return compute_identity(root, file_path)
