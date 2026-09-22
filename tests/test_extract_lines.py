"""Public PDF extraction keeps source lines alongside normalized text."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from doc_lineage.extract import ExtractCache, extract
from doc_lineage.extract.ocr import CallableOCRBackend

METRIC_LINES = (
    "AAL  $600 million",
    "AVA  $0.5 billion",
    "Funded ratio  0.8",
    "Discount rate  6%",
    "Funded ratio | 2023 | 2024 | 78.0% | 80.0%",
)


def _metric_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path), invariant=1)
    for index, line in enumerate(METRIC_LINES):
        pdf.drawString(72, 720 - index * 24, line)
    pdf.showPage()
    pdf.drawString(72, 720, "Participant count  120000")
    pdf.showPage()
    pdf.save()


def test_pdf_preserves_metric_lines_and_normalized_text(tmp_path: Path) -> None:
    source = tmp_path / "metrics.pdf"
    _metric_pdf(source)
    document = extract(source, ocr_enabled=False, cache=ExtractCache())

    assert document.spans[0].text_lines == METRIC_LINES
    assert document.spans[0].text == " ".join(" ".join(METRIC_LINES).split())
    assert document.spans[0].page == 1
    assert document.spans[1].text_lines == ("Participant count  120000",)
    assert document.spans[1].page == 2
    assert document.coverage.pages_with_text_layer == 2


def test_line_data_survives_fresh_disk_cache(tmp_path: Path, monkeypatch) -> None:
    from doc_lineage.extract import pdf as pdf_module

    source = tmp_path / "metrics.pdf"
    _metric_pdf(source)
    cache_root = tmp_path / "cache"
    first = extract(source, ocr_enabled=False, cache=ExtractCache(cache_root))

    def unexpected_extraction(*args, **kwargs):
        pytest.fail("a valid cache entry should retain lines without re-extraction")

    monkeypatch.setattr(pdf_module, "_extract_pdf_page", unexpected_extraction)
    second = extract(source, ocr_enabled=False, cache=ExtractCache(cache_root))
    assert second == first
    assert second.spans[0].text_lines == METRIC_LINES


@pytest.mark.parametrize("cached_lines", [None, "not-a-line-array", [7], []])
def test_legacy_or_invalid_native_lines_are_refreshed(tmp_path: Path, cached_lines) -> None:
    source = tmp_path / "metrics.pdf"
    _metric_pdf(source)
    cache_root = tmp_path / "cache"
    first = extract(source, ocr_enabled=False, cache=ExtractCache(cache_root))
    entry = cache_root / first.stable_id / "page-1.json"
    payload = json.loads(entry.read_text())
    span = payload["spans"][0]
    if cached_lines is None:
        span.pop("text_lines")
    else:
        span["text_lines"] = cached_lines
    span["text"] = "stale flattened content"
    entry.write_text(json.dumps(payload))

    second = extract(source, ocr_enabled=False, cache=ExtractCache(cache_root))
    assert second.spans[0].text_lines == METRIC_LINES
    assert second.spans[0].text == first.spans[0].text
    assert json.loads(entry.read_text())["spans"][0]["text_lines"] == list(METRIC_LINES)


def test_ocr_lines_preserve_page_number_after_unreadable_gap(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    pdf = canvas.Canvas(str(source), invariant=1)
    pdf.showPage()  # unreadable page one must not renumber the recognized page
    image = Image.new("RGB", (240, 120), "white")
    image.paste("black", (20, 50, 220, 70))
    pdf.drawImage(ImageReader(image), 72, 600, width=240, height=120)
    pdf.showPage()
    pdf.save()
    seen: list[tuple[int, int]] = []
    recognized = "AAL  $600 million\nAVA  $0.5 billion"

    def recognize(rendered: Image.Image, *, rotation: int = 0) -> str | None:
        seen.append(rendered.size)
        return recognized if rendered.convert("L").getextrema()[0] < 128 else None

    document = extract(source, ocr_backend=CallableOCRBackend(recognize), cache=ExtractCache())
    assert len(seen) == 2 and all(min(size) > 1 for size in seen)
    assert document.coverage.pages_unreadable == 1
    assert document.coverage.pages_recognized == 1
    assert len(document.spans) == 1
    assert document.spans[0].page == 2
    assert document.spans[0].text == recognized
    assert document.spans[0].text_lines == tuple(recognized.splitlines())


def test_legacy_ocr_cache_recovers_lines_without_recognition(tmp_path: Path) -> None:
    payload = {
        "ocr_mode": "ocr",
        "spans": [{"text": "first row\nsecond row", "page": 2, "bbox": None, "source": "ocr"}],
    }
    root = tmp_path / "cache"
    entry = root / "identity" / "page-2.json"
    entry.parent.mkdir(parents=True)
    entry.write_text(json.dumps(payload))
    spans = ExtractCache(root).get("identity", 2, "ocr")
    assert spans is not None
    assert spans[0].text_lines == ("first row", "second row")
    assert spans[0].page == 2


def test_malformed_legacy_ocr_text_is_reextracted(tmp_path: Path) -> None:
    source = tmp_path / "metrics.pdf"
    _metric_pdf(source)
    cache_root = tmp_path / "cache"
    first = extract(source, ocr_enabled=False, cache=ExtractCache(cache_root))
    entry = cache_root / first.stable_id / "page-1.json"
    payload = json.loads(entry.read_text())
    payload["spans"][0].update(source="ocr", text=None)
    payload["spans"][0].pop("text_lines")
    entry.write_text(json.dumps(payload))

    second = extract(source, ocr_enabled=False, cache=ExtractCache(cache_root))
    assert second.spans[0] == first.spans[0]
    assert json.loads(entry.read_text())["spans"][0]["source"] == "text_layer"


def test_pdf_source_lines_keep_boundary_whitespace(tmp_path: Path) -> None:
    from pypdf import PdfReader

    source = tmp_path / "whitespace.pdf"
    pdf = canvas.Canvas(str(source), invariant=1)
    pdf.drawString(72, 720, "  First line")
    pdf.drawString(72, 696, "Last line  ")
    pdf.save()
    raw_text = PdfReader(str(source)).pages[0].extract_text()
    assert raw_text.startswith("  First line")
    assert "Last line  " in raw_text

    document = extract(source, ocr_enabled=False, cache=ExtractCache())
    assert document.spans[0].text_lines == tuple(raw_text.splitlines())
    assert document.spans[0].text == "First line Last line"
