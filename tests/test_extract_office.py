"""Word and PowerPoint extraction smoke tests."""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from pptx import Presentation

from doc_lineage.extract import ExtractCache, extract, reset_cache


def test_extract_docx_returns_paragraph_spans(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    doc = DocxDocument()
    doc.add_paragraph("First paragraph")
    doc.add_paragraph("Second paragraph")
    doc.save(str(path))

    reset_cache(ExtractCache(tmp_path / "cache"))
    document = extract(path, cache=ExtractCache(tmp_path / "cache"))

    assert len(document.spans) == 2
    assert all(span.source == "text_layer" for span in document.spans)
    assert document.coverage.pages_with_text_layer == 2


def test_extract_pptx_returns_slide_spans(tmp_path: Path) -> None:
    path = tmp_path / "sample.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Slide title"
    presentation.save(str(path))

    reset_cache(ExtractCache(tmp_path / "cache2"))
    document = extract(path, cache=ExtractCache(tmp_path / "cache2"))

    assert document.spans
    assert document.spans[0].page == 1
    assert document.spans[0].source == "text_layer"
