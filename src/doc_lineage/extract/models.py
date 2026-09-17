"""Data models for document extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SpanSource = Literal["text_layer", "ocr"]


@dataclass(frozen=True)
class Span:
    """One extracted text span with page pointer and provenance."""

    text: str
    page: int
    bbox: tuple[float, float, float, float] | None
    source: SpanSource


@dataclass(frozen=True)
class CoverageStats:
    """Per-document extraction coverage; all three counts are always reported."""

    pages_with_text_layer: int
    pages_recognized: int
    pages_unreadable: int


@dataclass(frozen=True)
class Document:
    """Extracted document with stable identity and spans."""

    stable_id: str
    spans: list[Span]
    coverage: CoverageStats
