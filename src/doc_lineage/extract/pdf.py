"""PDF extraction with per-page text-layer detection and OCR fallback."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from doc_lineage.extract.models import CoverageStats, Document, Span

if TYPE_CHECKING:
    from PIL.Image import Image

    from doc_lineage.extract.cache import ExtractCache, OCRMode
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
    # The recognition mode is part of the cache identity: an empty result from a
    # run with OCR off must not be replayed to a later run with OCR on.
    mode: OCRMode = "ocr" if (ocr_enabled and ocr_backend is not None) else "off"

    for page_index, page in enumerate(reader.pages, start=1):
        cached = cache.get(stable_id, page_index, mode)
        if cached and any(
            span.source == "text_layer" and span.text_lines is None for span in cached
        ):
            # Old native-text entries have already lost their line boundaries.
            # Re-extract from the PDF rather than inventing lines from flat text.
            cached = None
        if cached is not None:
            spans.extend(cached)
            outcome = _page_outcome(cached)
        else:
            page_spans, outcome = _extract_pdf_page(page, page_index, ocr_backend, ocr_enabled)
            cache.put(stable_id, page_index, page_spans, mode)
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
    raw_text = page.extract_text() or ""
    text = raw_text.strip()
    rotation = int(page.get("/Rotate", 0) or 0)

    if text:
        span = Span(
            text=_normalize_reading_order(text),
            page=page_number,
            bbox=None,
            source="text_layer",
            text_lines=tuple(raw_text.splitlines()),
        )
        return [span], "text_layer"

    if not ocr_enabled or ocr_backend is None:
        return [], "unreadable"

    image = _render_page_image(page)
    if image is None:
        # No page renderer available, so this page was never actually looked at.
        # Reporting it as unreadable is the whole point of the coverage contract.
        return [], "unreadable"
    recognized = ocr_backend.recognize(image, rotation=rotation)
    if recognized:
        span = Span(
            text=recognized,
            page=page_number,
            bbox=None,
            source="ocr",
            text_lines=tuple(recognized.splitlines()),
        )
        return [span], "ocr"

    return [], "unreadable"


def _normalize_reading_order(text: str) -> str:
    """Collapse the whitespace that rotated and watermarked layouts introduce.

    ``pypdf.PageObject.extract_text`` already applies the page's ``/Rotate``
    entry, so the text arrives in reading order; what it does not do is collapse
    the ragged runs of spaces and newlines that a rotated text matrix or a
    diagonal watermark leaves behind.
    """
    return " ".join(text.split())


def _render_page_image(page: object) -> Image | None:
    """Render one page to an image, or return ``None`` when that is impossible.

    A missing renderer is an unreadable page, not a blank one: returning a
    placeholder image here would let any supplied OCR backend "recognize" an
    empty page and report it as read.
    """
    from pypdf import PageObject

    assert isinstance(page, PageObject)
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None

    import io

    from pypdf import PdfWriter

    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(buffer)
    try:
        doc = pdfium.PdfDocument(buffer.getvalue())
    except Exception:  # noqa: BLE001 - any pdfium failure is an unreadable page
        return None
    try:
        rendered: Image = doc[0].render(scale=2).to_pil()
    except Exception:  # noqa: BLE001 - see above
        return None
    finally:
        doc.close()
    return rendered
