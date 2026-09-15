"""Document identity derived from content and library path conventions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

NUMERIC_PREFIX_PATTERN = re.compile(r"^(?P<prefix>\d+)[\-_.](?P<rest>.+)$")
YEAR_PATTERN = re.compile(r"^\d{4}$")


@dataclass(frozen=True)
class DocumentIdentity:
    """Stable identity for one document file."""

    stable_id: str
    sha256: str
    doc_key: str
    entity_slug: str
    category: str
    as_of: str
    filename: str
    supersession_evidence: str | None = None


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase hex digest for raw document bytes."""
    return hashlib.sha256(data).hexdigest()


def parse_path_parts(root: Path, file_path: Path) -> tuple[str, str, str]:
    """Parse entity slug, category, and as-of segment from a library path."""
    relative = file_path.relative_to(root)
    parts = relative.parts
    if len(parts) < 3:
        msg = f"path must be <entity>/<category>/.../file: {relative}"
        raise ValueError(msg)

    entity_slug = parts[0]
    category = parts[1]
    as_of = _parse_as_of(parts[2:-1], file_path.name)
    return entity_slug, category, as_of


def _parse_as_of(intermediate_parts: tuple[str, ...], filename: str) -> str:
    # Archive and other organizational folders do not erase the document year.
    # The nearest year directory retains precedence over filename metadata.
    for part in reversed(intermediate_parts):
        if YEAR_PATTERN.fullmatch(part):
            return part

    stem = Path(filename).stem
    year_match = re.search(r"(20\d{2})", stem)
    if year_match:
        return year_match.group(1)
    return "unknown"


def build_doc_key(entity_slug: str, category: str, as_of: str) -> str:
    """Return the canonical doc key for one library location."""
    return f"{entity_slug}/{category}/{as_of}"


def compute_identity(
    root: Path,
    file_path: Path,
    *,
    content: bytes | None = None,
) -> DocumentIdentity:
    """Compute content-first identity for one document under ``root``."""
    raw = content if content is not None else file_path.read_bytes()
    digest = sha256_bytes(raw)
    entity_slug, category, as_of = parse_path_parts(root, file_path)
    doc_key = build_doc_key(entity_slug, category, as_of)
    return DocumentIdentity(
        stable_id=digest,
        sha256=digest,
        doc_key=doc_key,
        entity_slug=entity_slug,
        category=category,
        as_of=as_of,
        filename=file_path.name,
    )


def parse_numeric_prefix(filename: str) -> tuple[int | None, str, str | None]:
    """Return numeric prefix, normalized basename, and convention name if matched."""
    match = NUMERIC_PREFIX_PATTERN.match(filename)
    if not match:
        return None, filename, None
    prefix = int(match.group("prefix"))
    rest = match.group("rest")
    return prefix, rest, "numeric_prefix_separator"


def normalized_supersession_group(filename: str) -> str:
    """Group superseding files that share the same basename after numeric prefix."""
    basename = Path(filename).name
    _prefix, rest, _convention = parse_numeric_prefix(basename)
    return Path(rest).stem.lower()
