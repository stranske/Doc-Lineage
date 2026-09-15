"""PDF extraction with per-page text-layer detection and OCR fallback."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from doc_lineage.extract.models import CoverageStats, Document, Span

if TYPE_CHECKING:
    from doc_lineage.extract.cache import ExtractCache
    from doc_lineage.extract.ocr import OCRBackend


def extract_pdf(
    path: Path,
    stable_id: str,
    *,
    cache: ExtractCache,
    ocr_backend: OCRBackend | None,
    ocr_enabled: bool,
) -> Document:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    spans: list[Span] = []
    pages_with_text_layer = 0
    pages_recognized = 0
    pages_unreadable = 0

    for page_index, page in enumerate(reader.pages, start=1):
        cached = cache.get(stable_id, page_index)
        if cached is not None:
            spans.extend(cached)
            outcome = _page_outcome(cached)
            pages_with_text_layer += int(outcome == "text_layer")
            pages_recognized += int(outcome == "ocr")
            pages_unreadable += int(outcome == "unreadable")
            continue

        page_spans, outcome = _extract_pdf_page(page, page_index, ocr_backend, ocr_enabled)
        cache.put(stable_id, page_index, page_spans)
        spans.extend(page_spans)
        pages_with_text_layer += int(outcome == "text_layer")
        pages_recognized += int(outcome == "ocr")
        pages_unreadable += int(outcome == "unreadable")

    coverage = CoverageStats(
        pages_with_text_layer=pages_with_text_layer,
        pages_recognized=pages_recognized,
        pages_unreadable=pages_unreadable,
    )
    return Document(stable_id=stable_id, spans=spans, coverage=coverage)


def _page_outcome(spans: list[Span]) -> str:
    if not spans:
        return "unreadable"
    if any(span.source == "text_layer" for span in spans):
        return "text_layer"
    return "ocr"


def _extract_pdf_page(
    page: object,
    page_number: int,
    ocr_backend: OCRBackend | None,
    ocr_enabled: bool,
) -> tuple[list[Span], str]:
    from pypdf import PageObject

    assert isinstance(page, PageObject)
    text = (page.extract_text() or "").strip()
    rotation = int(page.get("/Rotate", 0) or 0)

    if text:
        span = Span(
            text=_normalize_reading_order(text, rotation),
            page=page_number,
            bbox=None,
            source="text_layer",
        )
        return [span], "text_layer"

    if not ocr_enabled or ocr_backend is None:
        return [], "unreadable"

    image = _render_page_image(page)
    recognized = ocr_backend.recognize(image, rotation=rotation)
    if recognized:
        span = Span(
            text=recognized,
            page=page_number,
            bbox=None,
            source="ocr",
        )
        return [span], "ocr"

    return [], "unreadable"


def _normalize_reading_order(text: str, rotation: int) -> str:
    normalized = " ".join(text.split())
    if rotation % 360 == 0:
        return normalized
    return normalized


def _render_page_image(page: object) -> object:
    from PIL import Image
    from pypdf import PageObject

    assert isinstance(page, PageObject)
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return Image.new("RGB", (1, 1), color="white")

    import io

    from pypdf import PdfWriter

    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(buffer)
    doc = pdfium.PdfDocument(buffer.getvalue())
    rendered = doc[0].render(scale=2).to_pil()
    doc.close()
    return rendered
