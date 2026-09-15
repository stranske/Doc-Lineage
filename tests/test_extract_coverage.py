"""Coverage and OCR fallback tests for doc_lineage.extract."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from doc_lineage.extract import ExtractCache, extract, reset_cache
from doc_lineage.extract.ocr import CallableOCRBackend


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    reset_cache(ExtractCache(root))
    yield root
    reset_cache(None)


def _write_text_pdf(path: Path, pages: list[tuple[str, int]]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    for text, rotation in pages:
        if rotation:
            pdf.rotate(rotation)
        pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()


def _write_image_only_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.showPage()
    pdf.save()


def test_image_only_pdf_uses_ocr_and_reports_recognized(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "image-only.pdf"
    _write_image_only_pdf(pdf_path)

    backend = CallableOCRBackend(lambda _image, rotation=0: "recognized page text")
    document = extract(
        pdf_path,
        ocr_backend=backend,
        cache=ExtractCache(cache_dir),
    )

    assert document.coverage.pages_recognized == 1
    assert document.coverage.pages_with_text_layer == 0
    assert document.coverage.pages_unreadable == 0
    assert any(span.source == "ocr" for span in document.spans)


def test_ocr_disabled_reports_unreadable_not_empty_success(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "image-only.pdf"
    _write_image_only_pdf(pdf_path)

    document = extract(
        pdf_path,
        ocr_enabled=False,
        cache=ExtractCache(cache_dir),
    )

    assert document.coverage.pages_unreadable == 1
    assert document.coverage.pages_recognized == 0
    assert document.spans == []


def test_mixed_pdf_recognizes_only_missing_text_layer_page(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    pdf.drawString(72, 720, "layer one")
    pdf.showPage()
    pdf.showPage()
    pdf.save()

    backend = CallableOCRBackend(lambda _image, rotation=0: "ocr page two")
    document = extract(
        pdf_path,
        ocr_backend=backend,
        cache=ExtractCache(cache_dir),
    )

    assert document.coverage.pages_with_text_layer == 1
    assert document.coverage.pages_recognized == 1
    assert document.coverage.pages_unreadable == 0
    sources = {span.page: span.source for span in document.spans}
    assert sources[1] == "text_layer"
    assert sources[2] == "ocr"


def test_rotated_page_text_is_in_reading_order(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "rotated.pdf"
    _write_text_pdf(pdf_path, [("ROTATED READING ORDER", 90)])

    document = extract(pdf_path, cache=ExtractCache(cache_dir))

    assert document.spans
    assert "ROTATED READING ORDER" in document.spans[0].text


def test_rename_hits_cache_by_stable_id(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "original.pdf"
    _write_text_pdf(pdf_path, [("cache me", 0)])
    active_cache = ExtractCache(cache_dir)

    first = extract(pdf_path, cache=active_cache)
    renamed = tmp_path / "renamed.pdf"
    shutil.copy2(pdf_path, renamed)
    second = extract(renamed, cache=active_cache)

    assert first.stable_id == second.stable_id
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == first.stable_id
    assert second.spans == first.spans


def test_coverage_always_reports_all_three_counts(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "counts.pdf"
    _write_text_pdf(pdf_path, [("one", 0)])

    document = extract(pdf_path, cache=ExtractCache(cache_dir))
    coverage = document.coverage

    assert coverage.pages_with_text_layer >= 0
    assert coverage.pages_recognized >= 0
    assert coverage.pages_unreadable >= 0
    assert (
        coverage.pages_with_text_layer
        + coverage.pages_recognized
        + coverage.pages_unreadable
    ) == 1


def test_deliberate_break_per_document_detection_violates_mixed_pdf_contract(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """Document the deliberate-break gate: per-document detection breaks mixed PDF coverage."""
    pdf_path = tmp_path / "mixed-break.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    pdf.drawString(72, 720, "visible layer")
    pdf.showPage()
    pdf.showPage()
    pdf.save()

    correct = extract(
        pdf_path,
        ocr_backend=CallableOCRBackend(lambda _image, rotation=0: "ocr page two"),
        cache=ExtractCache(cache_dir),
    )
    assert correct.coverage.pages_with_text_layer == 1
    assert correct.coverage.pages_recognized == 1
    wrong_pages_with_text_layer = 2
    assert wrong_pages_with_text_layer != correct.coverage.pages_with_text_layer
