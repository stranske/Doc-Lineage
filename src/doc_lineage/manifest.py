"""Incremental manifest generation over a document library tree."""

from __future__ import annotations

import errno
import json
import logging
import mimetypes
import os
import stat
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from doc_lineage.adapters.docling_segmenter import MAX_INGEST_BYTES
from doc_lineage.identity import (
    DocumentIdentity,
    compute_identity,
    normalized_supersession_group,
    parse_numeric_prefix,
)

TEXT_LAYER_VALUES = frozenset({"present", "absent", "unknown"})
LOGGER = logging.getLogger(__name__)
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


def _received_at(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _guess_mime(path: Path) -> str:
    mime, _encoding = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def _iter_documents(root: Path) -> list[Path]:
    resolved_root = root.resolve()
    documents: list[Path] = []
    for path in sorted(resolved_root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in DOCUMENT_SUFFIXES:
            continue
        if not path.resolve().is_relative_to(resolved_root):
            continue
        documents.append(path)
    return documents


def _read_document_under_root(root_fd: int, relative: Path) -> tuple[bytes, os.stat_result] | None:
    """Read bytes and metadata from one root-anchored, no-follow file descriptor."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError("secure manifest scanning requires no-follow directory opens")
    directory_fd = os.dup(root_fd)
    try:
        for part in relative.parts[:-1]:
            next_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        with os.fdopen(file_fd, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                return None
            if metadata.st_size > MAX_INGEST_BYTES:
                LOGGER.warning(
                    "Skipping document %s: exceeds ingest size limit (%s > %s bytes)",
                    relative,
                    metadata.st_size,
                    MAX_INGEST_BYTES,
                )
                return None
            content = source.read(MAX_INGEST_BYTES + 1)
            if len(content) > MAX_INGEST_BYTES:
                LOGGER.warning(
                    "Skipping document %s: exceeds ingest size limit (%s > %s bytes)",
                    relative,
                    len(content),
                    MAX_INGEST_BYTES,
                )
                return None
            return content, metadata
    except OSError as error:
        # A candidate can disappear or become a symlink after directory traversal.
        # I/O, permissions, or descriptor exhaustion must fail the manifest.
        if error.errno in {errno.ENOENT, errno.ENOTDIR, errno.ELOOP}:
            return None
        raise
    finally:
        os.close(directory_fd)


def _assign_supersedes(rows: list[ManifestRow]) -> list[ManifestRow]:
    """Link increasing numeric prefixes, treating an unnumbered file as the original.

    Equal prefixes do not establish an order. If a rank has conflicting contents,
    leave links to and from that rank unset rather than choosing by path order.
    """
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
            ranks: dict[int, list[tuple[ManifestRow, str | None]]] = defaultdict(list)
            for row, prefix, convention in group:
                ranks[prefix if prefix is not None else -1].append((row, convention))
            ordered_ranks = sorted(ranks)
            for older_rank, newer_rank in zip(ordered_ranks, ordered_ranks[1:], strict=False):
                older_ids = {row.stable_id for row, _ in ranks[older_rank]}
                newer_ids = {row.stable_id for row, _ in ranks[newer_rank]}
                if len(older_ids) != 1 or len(newer_ids) != 1:
                    continue
                older_id = next(iter(older_ids))
                if older_ids == newer_ids:
                    # A byte-identical re-supply retains the prior version link;
                    # it must not supersede its own content identity.
                    predecessor = superseded_by.get(ranks[older_rank][0][0].path)
                    if predecessor is None:
                        continue
                    older_id = predecessor
                for newer_row, newer_conv in ranks[newer_rank]:
                    superseded_by[newer_row.path] = older_id
                    if newer_conv:
                        evidence_by_target[newer_row.path] = newer_conv

    updated: list[ManifestRow] = []
    for row in rows:
        supersedes = superseded_by.get(row.path)
        evidence = evidence_by_target.get(row.path)
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
    if not root.is_dir():
        raise ValueError(f"library root must be an existing directory: {root}")
    rows: list[ManifestRow] = []
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise RuntimeError("secure manifest scanning requires no-follow directory opens")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for file_path in _iter_documents(root):
            relative = file_path.relative_to(root)
            opened = _read_document_under_root(root_fd, relative)
            if opened is None:
                continue
            content, metadata = opened
            identity = compute_identity(root, file_path, content=content)
            rows.append(
                ManifestRow(
                    stable_id=identity.stable_id,
                    sha256=identity.sha256,
                    path=relative.as_posix(),
                    entity_slug=identity.entity_slug,
                    category=identity.category,
                    as_of=identity.as_of,
                    received_at=_received_at(metadata.st_mtime),
                    bytes=metadata.st_size,
                    mime=_guess_mime(file_path),
                    supersedes=None,
                    text_layer="unknown",
                )
            )
    finally:
        os.close(root_fd)
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
    root = root.resolve()
    output_path = output_path.resolve()
    if output_path.is_relative_to(root) and output_path.suffix.lower() in DOCUMENT_SUFFIXES:
        raise ValueError("manifest output must not be a document path inside the input root")
    rows = build_manifest_rows(root)
    previous_lines = read_manifest(output_path)
    # Text checks describe bytes, so even a reused path can inherit a result.
    annotations_by_identity: dict[tuple[str, str], set[str]] = defaultdict(set)
    for line in previous_lines.values():
        payload = json.loads(line)
        stable_id, digest = payload.get("stable_id"), payload.get("sha256")
        annotation = payload.get("text_layer")
        if (
            isinstance(stable_id, str)
            and isinstance(digest, str)
            and isinstance(annotation, str)
            and annotation in {"present", "absent"}
        ):
            annotations_by_identity[(stable_id, digest)].add(annotation)
    output_lines: list[str] = []
    for row in rows:
        serialized = row.to_json()
        previous = previous_lines.get(row.path)
        annotations = annotations_by_identity.get((row.stable_id, row.sha256), set())
        if len(annotations) == 1:
            serialized = replace(row, text_layer=next(iter(annotations))).to_json()
        if previous is not None:
            previous_payload = json.loads(previous)
            if (
                previous_payload.get("stable_id") == row.stable_id
                and previous_payload.get("sha256") == row.sha256
                and isinstance(previous_payload.get("text_layer"), str)
                and previous_payload.get("text_layer") in TEXT_LAYER_VALUES
            ):
                serialized = replace(row, text_layer=previous_payload["text_layer"]).to_json()
            current_payload = json.loads(serialized)
            if previous_payload == current_payload:
                serialized = previous
        output_lines.append(serialized)

    content = "\n".join(output_lines)
    if output_lines:
        content += "\n"
    if output_path.exists() and output_path.read_bytes() == content.encode("utf-8"):
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def identity_for_path(root: Path, file_path: Path) -> DocumentIdentity:
    """Expose identity computation for tests and callers."""
    return compute_identity(root, file_path)
