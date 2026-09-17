"""Document extraction with page pointers and optional OCR fallback."""

from __future__ import annotations

import os
from pathlib import Path

from doc_lineage.extract.cache import ExtractCache
from doc_lineage.extract.models import CoverageStats, Document, Span
from doc_lineage.extract.ocr import OCRBackend, default_ocr_backend
from doc_lineage.extract.office import extract_docx, extract_pptx, stable_id_for_bytes
from doc_lineage.extract.pdf import extract_pdf

__all__ = [
    "CoverageStats",
    "Document",
    "ExtractCache",
    "OCRBackend",
    "Span",
    "extract",
]

#: ``python-docx`` and ``python-pptx`` read OOXML only. The legacy binary
#: formats share a file-type name with them and nothing else, so routing one
#: through them raises an opaque parser error instead of saying what is wrong.
_LEGACY_BINARY_SUFFIXES = {".doc": ".docx", ".ppt": ".pptx"}

_GLOBAL_CACHE: ExtractCache | None = None


def _cache_root() -> Path:
    override = os.environ.get("DOC_LINEAGE_EXTRACT_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "doc_lineage" / "extract"


def _get_cache() -> ExtractCache:
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = ExtractCache(_cache_root())
    return _GLOBAL_CACHE


def reset_cache(cache: ExtractCache | None = None) -> None:
    """Reset the module cache (primarily for tests)."""
    global _GLOBAL_CACHE
    _GLOBAL_CACHE = cache


def extract(
    path: str | Path,
    *,
    ocr_enabled: bool = True,
    ocr_backend: OCRBackend | None = None,
    cache: ExtractCache | None = None,
) -> Document:
    """Extract text spans with page pointers from a supported document."""
    file_path = Path(path)
    content = file_path.read_bytes()
    stable_id = stable_id_for_bytes(content)
    active_cache = cache if cache is not None else _get_cache()
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        backend = ocr_backend if ocr_backend is not None else default_ocr_backend()
        return extract_pdf(
            file_path,
            stable_id,
            cache=active_cache,
            ocr_backend=backend,
            ocr_enabled=ocr_enabled,
        )
    if suffix == ".docx":
        return extract_docx(file_path, stable_id, cache=active_cache)
    if suffix == ".pptx":
        return extract_pptx(file_path, stable_id, cache=active_cache)
    if suffix in _LEGACY_BINARY_SUFFIXES:
        msg = (
            f"unsupported document type: {suffix} is the legacy binary format; "
            f"convert it to {_LEGACY_BINARY_SUFFIXES[suffix]} first"
        )
        raise ValueError(msg)

    msg = f"unsupported document type: {suffix}"
    raise ValueError(msg)
