"""Opt-in regression for the default local Tesseract ingest backend."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from doc_lineage.ingest import ingest_document

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_lpa.pdf"


def _rasterize_to_image_only_pdf(source: Path, destination: Path) -> None:
    """Write a visual-only copy so the ingest path must use OCR."""
    import pypdfium2 as pdfium
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    rendered = pdfium.PdfDocument(source)
    pdf = canvas.Canvas(str(destination), pagesize=letter)
    try:
        for page in rendered:
            image = page.render(scale=3).to_pil()
            width, height = letter
            pdf.drawImage(ImageReader(image), 0, 0, width=width, height=height)
            pdf.showPage()
    finally:
        rendered.close()
    pdf.save()


@pytest.mark.real_tesseract
def test_default_backend_recovers_image_only_pdf(tmp_path: Path) -> None:
    """The installed default backend recovers the committed LPA's key terms."""
    if os.environ.get("DOC_LINEAGE_REAL_TESSERACT") != "1":
        pytest.skip("set DOC_LINEAGE_REAL_TESSERACT=1 to run the real Tesseract smoke")

    from pypdf import PdfReader

    image_only = tmp_path / "synthetic-lpa-image-only.pdf"
    _rasterize_to_image_only_pdf(FIXTURE, image_only)
    assert all(not (page.extract_text() or "").strip() for page in PdfReader(image_only).pages)

    result = ingest_document(image_only, output_dir=tmp_path / "ingest", allow_docling=False)

    assert result.pages_without_text_layer == (1, 2)
    assert result.unreadable_pages == ()
    assert result.coverage_status == "complete"
    assert {segment.page for segment in result.segments} == {1, 2}
    assert all(segment.method == "ocr" for segment in result.segments)
    recovered = " ".join(segment.text for segment in result.segments).upper()
    assert "MANAGEMENT FEE" in recovered
    assert "1.75" in recovered
