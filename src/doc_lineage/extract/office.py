"""Word and PowerPoint extraction returning the same span shape."""

from __future__ import annotations

import hashlib
from pathlib import Path

from doc_lineage.extract.models import CoverageStats, Document, Span


def extract_docx(path: Path, stable_id: str) -> Document:
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    spans: list[Span] = []
    for index, paragraph in enumerate(doc.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue
        spans.append(
            Span(
                text=text,
                page=index,
                bbox=None,
                source="text_layer",
            )
        )
    coverage = CoverageStats(
        pages_with_text_layer=len(spans),
        pages_recognized=0,
        pages_unreadable=0,
    )
    return Document(stable_id=stable_id, spans=spans, coverage=coverage)


def extract_pptx(path: Path, stable_id: str) -> Document:
    from pptx import Presentation

    presentation = Presentation(str(path))
    spans: list[Span] = []
    for slide_index, slide in enumerate(presentation.slides, start=1):
        texts = []
        for shape in slide.shapes:
            if not hasattr(shape, "text"):
                continue
            text = shape.text.strip()
            if text:
                texts.append(text)
        if texts:
            spans.append(
                Span(
                    text="\n".join(texts),
                    page=slide_index,
                    bbox=None,
                    source="text_layer",
                )
            )
    coverage = CoverageStats(
        pages_with_text_layer=len(spans),
        pages_recognized=0,
        pages_unreadable=0,
    )
    return Document(stable_id=stable_id, spans=spans, coverage=coverage)


def stable_id_for_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
