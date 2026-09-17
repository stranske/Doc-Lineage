"""Adapters that wrap third-party document tooling behind a stable interface."""

from doc_lineage.adapters.docling_segmenter import (
    DOCLING_BACKEND,
    OFFLINE_BACKEND,
    PageText,
    SegmenterResult,
    segment_document,
)

__all__ = [
    "DOCLING_BACKEND",
    "OFFLINE_BACKEND",
    "PageText",
    "SegmenterResult",
    "segment_document",
]
