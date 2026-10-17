"""Coverage and OCR fallback tests for doc_lineage.extract."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from doc_lineage.extract import ExtractCache, extract, reset_cache
from doc_lineage.extract.ocr import CallableOCRBackend

ROTATED_READING_ORDER = "ROTATED READING ORDER"


@pytest.fixture
def cache_dir(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "cache"
    reset_cache(ExtractCache(root))
    yield root
    reset_cache(None)


def _write_text_pdf(path: Path, pages: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    for text in pages:
        pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()


def _set_page_rotation(path: Path, rotation: int) -> None:
    """Set the page's ``/Rotate`` entry, which is what extraction reads.

    ``canvas.rotate()`` only rotates the content transformation matrix, so a PDF
    written that way has no ``/Rotate`` entry at all and exercises nothing.
    """
    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(rotation)
        writer.add_page(page)
    with path.open("wb") as stream:
        writer.write(stream)


def _write_image_only_pdf(path: Path) -> None:
    """Write a one-page PDF whose only content is a raster image.

    An empty page would also have no text layer, but it would let a stub OCR
    backend "recognize" a page that has nothing on it, so the test would pass
    against an implementation that never renders anything.
    """
    image = Image.new("RGB", (240, 120), color="white")
    for x in range(20, 220):
        for y in range(50, 70):
            image.putpixel((x, y), (0, 0, 0))
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.drawImage(ImageReader(image), 72, 600, width=240, height=120)
    pdf.showPage()
    pdf.save()


def test_image_only_pdf_uses_ocr_and_reports_recognized(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "image-only.pdf"
    _write_image_only_pdf(pdf_path)

    seen: list[tuple[int, int]] = []

    def recognizer(image: Image.Image, *, rotation: int = 0) -> str:
        seen.append(image.size)
        return "recognized page text"

    backend = CallableOCRBackend(recognizer)
    document = extract(
        pdf_path,
        ocr_backend=backend,
        cache=ExtractCache(cache_dir),
    )

    assert document.coverage.pages_recognized == 1
    assert document.coverage.pages_with_text_layer == 0
    assert document.coverage.pages_unreadable == 0
    assert any(span.source == "ocr" for span in document.spans)
    # The backend must have been handed a real rendered page, not a placeholder.
    assert seen and min(seen[0]) > 1


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


def test_unreadable_from_disabled_ocr_does_not_poison_a_later_ocr_run(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """A cached empty page from an OCR-off run must not survive into an OCR-on run."""
    pdf_path = tmp_path / "image-only.pdf"
    _write_image_only_pdf(pdf_path)
    active_cache = ExtractCache(cache_dir)

    first = extract(pdf_path, ocr_enabled=False, cache=active_cache)
    assert first.coverage.pages_unreadable == 1

    second = extract(
        pdf_path,
        ocr_backend=CallableOCRBackend(lambda _image, rotation=0: "recovered by ocr"),
        cache=active_cache,
    )

    assert second.coverage.pages_recognized == 1
    assert second.coverage.pages_unreadable == 0
    assert [span.text for span in second.spans] == ["recovered by ocr"]


def test_missing_page_renderer_reports_unreadable(
    cache_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No renderer means the page was never looked at, so it is unreadable."""
    from doc_lineage.extract import pdf as pdf_module

    pdf_path = tmp_path / "image-only.pdf"
    _write_image_only_pdf(pdf_path)
    monkeypatch.setattr(pdf_module, "_render_page_image", lambda _page: None)

    document = extract(
        pdf_path,
        ocr_backend=CallableOCRBackend(lambda _image, rotation=0: "should never be called"),
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
    _write_text_pdf(pdf_path, [ROTATED_READING_ORDER])
    _set_page_rotation(pdf_path, 90)

    reader = PdfReader(str(pdf_path))
    assert int(reader.pages[0].get("/Rotate", 0) or 0) == 90

    document = extract(pdf_path, cache=ExtractCache(cache_dir))

    assert document.spans
    assert document.spans[0].text == ROTATED_READING_ORDER


def test_rotation_is_forwarded_to_the_ocr_backend(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "rotated-image.pdf"
    _write_image_only_pdf(pdf_path)
    _set_page_rotation(pdf_path, 270)

    rotations: list[int] = []

    def recognizer(_image: Image.Image, *, rotation: int = 0) -> str:
        rotations.append(rotation)
        return "rotated ocr text"

    extract(pdf_path, ocr_backend=CallableOCRBackend(recognizer), cache=ExtractCache(cache_dir))

    assert rotations == [270]


def test_rename_hits_cache_by_stable_id(
    cache_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The renamed file must be served from the cache, not re-parsed.

    Comparing the two span lists proves nothing on its own: an implementation
    that re-parses the renamed file returns exactly the same spans. Counting
    page extractions is what separates a cache hit from a repeat extraction.
    """
    from doc_lineage.extract import pdf as pdf_module

    pdf_path = tmp_path / "original.pdf"
    _write_text_pdf(pdf_path, ["cache me"])
    active_cache = ExtractCache(cache_dir)

    extractions: list[int] = []
    real_extract_page = pdf_module._extract_pdf_page

    def counting_extract_page(page, page_number, ocr_backend, ocr_enabled):  # type: ignore[no-untyped-def]
        extractions.append(page_number)
        return real_extract_page(page, page_number, ocr_backend, ocr_enabled)

    monkeypatch.setattr(pdf_module, "_extract_pdf_page", counting_extract_page)

    first = extract(pdf_path, cache=active_cache)
    assert extractions == [1]

    renamed = tmp_path / "renamed.pdf"
    shutil.copy2(pdf_path, renamed)
    second = extract(renamed, cache=active_cache)

    assert extractions == [1], "renamed file re-extracted instead of hitting the cache"
    assert first.stable_id == second.stable_id
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == first.stable_id
    assert second.spans == first.spans


def test_malformed_cache_entry_is_a_miss_not_a_crash(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupt-cache.pdf"
    _write_text_pdf(pdf_path, ["still extractable"])
    active_cache = ExtractCache(cache_dir)

    first = extract(pdf_path, cache=active_cache)
    entry = cache_dir / first.stable_id / "page-1.json"
    assert entry.exists()
    entry.write_text("{ truncated", encoding="utf-8")

    second = extract(pdf_path, cache=ExtractCache(cache_dir))

    assert [span.text for span in second.spans] == [span.text for span in first.spans]
    assert json.loads(entry.read_text(encoding="utf-8"))["spans"]


@pytest.mark.parametrize("reopen_cache", [False, True], ids=["shared-memory", "reopened-disk"])
def test_pdf_replacement_keeps_snapshot_identity_and_cached_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reopen_cache: bool
) -> None:
    from doc_lineage.extract import pdf as pdf_module

    path = tmp_path / "snapshot.pdf"
    _write_text_pdf(path, ["Original snapshot"])
    original = path.read_bytes()
    _write_text_pdf(path, ["Revised on disk"])
    revised = path.read_bytes()
    path.write_bytes(original)
    read_bytes = Path.read_bytes

    def replace_after_read(candidate: Path) -> bytes:
        content = read_bytes(candidate)
        if candidate == path:
            candidate.write_bytes(revised)
        return content

    cache_root = tmp_path / "snapshot-cache"
    active_cache = ExtractCache(cache_root if reopen_cache else None)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", replace_after_read)
        first = extract(path, ocr_enabled=False, cache=active_cache)

    assert path.read_bytes() == revised
    assert first.stable_id == hashlib.sha256(original).hexdigest()
    assert [span.text for span in first.spans] == ["Original snapshot"]
    path.write_bytes(original)

    def fail_reextraction(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("original snapshot must be served from its cache")

    monkeypatch.setattr(pdf_module, "_extract_pdf_page", fail_reextraction)
    replay_cache = ExtractCache(cache_root) if reopen_cache else active_cache
    replay = extract(path, ocr_enabled=False, cache=replay_cache)
    assert replay.stable_id == first.stable_id
    assert replay.spans == first.spans
    assert [span.text for span in replay.spans] == ["Original snapshot"]


def test_cache_writes_are_atomic(cache_dir: Path, tmp_path: Path) -> None:
    """No partially written JSON is ever visible at the final cache path."""
    pdf_path = tmp_path / "atomic.pdf"
    _write_text_pdf(pdf_path, ["atomic write"])

    document = extract(pdf_path, cache=ExtractCache(cache_dir))
    entry = cache_dir / document.stable_id / "page-1.json"

    payload = json.loads(entry.read_text(encoding="utf-8"))
    assert payload["ocr_mode"] in {"off", "ocr"}
    assert payload["spans"][0]["text"] == "atomic write"
    assert list(entry.parent.glob("*.tmp")) == []


def test_partly_unreadable_pdf_reports_unreadable_page_identities(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """Cold and cache-hit extraction must agree on unreadable page identities.

    Deliberate-break gate: removing ``CoverageStats.unreadable_pages`` from
    ``src/doc_lineage/extract/models.py`` makes this regression fail (AttributeError
    or unexpected kwarg) while ``pages_unreadable`` alone would still pass a
    count-only check. Identities are recomputed from page outcomes; they are not
    stored in the cache.
    """
    pdf_path = tmp_path / "partly-unreadable.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    pdf.drawString(72, 720, "readable page one")
    pdf.showPage()
    pdf.save()
    _write_image_only_pdf(tmp_path / "image-only.pdf")
    reader = PdfReader(str(tmp_path / "image-only.pdf"))
    writer = PdfWriter()
    writer.add_page(PdfReader(str(pdf_path)).pages[0])
    writer.add_page(reader.pages[0])
    with pdf_path.open("wb") as stream:
        writer.write(stream)

    active_cache = ExtractCache(cache_dir)
    cold = extract(pdf_path, ocr_enabled=False, cache=active_cache)
    assert cold.coverage.pages_with_text_layer == 1
    assert cold.coverage.pages_unreadable == 1
    assert cold.coverage.unreadable_pages == (2,)
    assert len(cold.coverage.unreadable_pages) == cold.coverage.pages_unreadable

    cached = extract(pdf_path, ocr_enabled=False, cache=active_cache)
    assert cached.coverage.unreadable_pages == cold.coverage.unreadable_pages
    assert cached.coverage.pages_unreadable == cold.coverage.pages_unreadable
    assert cached.coverage.pages_with_text_layer == cold.coverage.pages_with_text_layer

    # Coverage is recomputed on every read; page cache entries store spans only.
    for entry in (cache_dir / cold.stable_id).glob("page-*.json"):
        payload = json.loads(entry.read_text(encoding="utf-8"))
        assert "coverage" not in payload
        assert "pages_unreadable" not in payload
        assert "unreadable_pages" not in payload
        assert "ocr_mode" in payload
        assert "spans" in payload


def test_retryable_ocr_runtime_error_reports_stable_unreadable_page_identities(
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    """Cold and repeated reads must agree on retryable-page identities.

    ``extract_pdf`` records identities for both ``\"unreadable\"`` and
    ``\"retryable\"``. OCR ``RuntimeError`` is retryable and is never written to
    the page cache, so each call re-extracts. A regression that only records
    identities on the OCR-off ``unreadable`` path would still pass
    ``test_partly_unreadable_pdf_reports_unreadable_page_identities``.

    Deliberate-break gate: changing ``pdf.py`` so retryable outcomes increment
    ``pages_unreadable`` without appending to ``unreadable_pages`` makes the
    identity assertions fail while a count-only check would still pass.
    """
    pdf_path = tmp_path / "retryable-identities.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    pdf.drawString(72, 720, "readable page one")
    pdf.showPage()
    pdf.save()
    _write_image_only_pdf(tmp_path / "image-only.pdf")
    reader = PdfReader(str(tmp_path / "image-only.pdf"))
    writer = PdfWriter()
    writer.add_page(PdfReader(str(pdf_path)).pages[0])
    writer.add_page(reader.pages[0])
    with pdf_path.open("wb") as stream:
        writer.write(stream)

    calls: list[tuple[int, int]] = []

    def failing(_image: Image.Image, *, rotation: int = 0) -> str:
        calls.append(_image.size)
        raise RuntimeError("stub OCR backend unavailable")

    active_cache = ExtractCache(cache_dir)
    backend = CallableOCRBackend(failing)

    cold = extract(pdf_path, ocr_backend=backend, cache=active_cache)
    assert cold.coverage.pages_with_text_layer == 1
    assert cold.coverage.pages_recognized == 0
    assert cold.coverage.pages_unreadable == 1
    assert cold.coverage.unreadable_pages == (2,)
    assert len(cold.coverage.unreadable_pages) == cold.coverage.pages_unreadable
    assert cold.spans and cold.spans[0].source == "text_layer"
    assert calls, "stub OCR must run so the outcome is retryable, not OCR-off unreadable"

    repeated = extract(pdf_path, ocr_backend=backend, cache=active_cache)
    assert repeated.coverage.unreadable_pages == cold.coverage.unreadable_pages
    assert repeated.coverage.pages_unreadable == cold.coverage.pages_unreadable
    assert len(calls) >= 2, "retryable pages must be re-extracted, not served from cache"

    # Retryable failures must not become completed cache entries.
    page2 = cache_dir / cold.stable_id / "page-2.json"
    assert not page2.exists()
    for entry in (cache_dir / cold.stable_id).glob("page-*.json"):
        payload = json.loads(entry.read_text(encoding="utf-8"))
        assert "coverage" not in payload
        assert "pages_unreadable" not in payload
        assert "unreadable_pages" not in payload


def test_coverage_always_reports_all_three_counts(cache_dir: Path, tmp_path: Path) -> None:
    pdf_path = tmp_path / "counts.pdf"
    _write_text_pdf(pdf_path, ["one"])

    document = extract(pdf_path, cache=ExtractCache(cache_dir))
    coverage = document.coverage

    assert coverage.pages_with_text_layer >= 0
    assert coverage.pages_recognized >= 0
    assert coverage.pages_unreadable >= 0
    assert (
        coverage.pages_with_text_layer + coverage.pages_recognized + coverage.pages_unreadable
    ) == 1
    assert len(coverage.unreadable_pages) == coverage.pages_unreadable


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


@pytest.mark.parametrize("result", ["empty", "exception"])
def test_failing_recognizer_reports_unreadable_without_spans(
    tmp_path: Path,
    cache_dir: Path,
    result: str,
) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    _write_image_only_pdf(pdf_path)

    def recognize(image, *, rotation=0):
        if result == "exception":
            raise RuntimeError("local recognizer unavailable")
        return "   "

    document = extract(
        pdf_path,
        ocr_backend=CallableOCRBackend(recognize),
        cache=ExtractCache(cache_dir),
    )
    assert document.spans == []
    assert document.coverage.pages_recognized == 0
    assert document.coverage.pages_unreadable == 1


def test_snapshot_page_recovery_can_recover_native_text_and_reject_bad_pages(
    tmp_path: Path,
) -> None:
    from doc_lineage.extract.pdf import recover_pdf_pages

    pdf_path = tmp_path / "native.pdf"
    _write_text_pdf(pdf_path, ["Native recovery"])
    spans = recover_pdf_pages(
        pdf_path.read_bytes(),
        [0, 1, 2],
        ocr_backend=CallableOCRBackend(lambda image, rotation=0: pytest.fail("native page OCR")),
    )
    assert len(spans) == 1 and spans[0].source == "text_layer" and spans[0].page == 1
    assert spans[0].text == "Native recovery"
    assert (
        recover_pdf_pages(
            b"%PDF-1.4\n%%EOF\n",
            [1],
            ocr_backend=CallableOCRBackend(
                lambda image, rotation=0: pytest.fail("invalid PDF OCR"),
            ),
        )
        == ()
    )


def test_failed_recognizer_remains_retryable_with_same_disk_cache(cache_dir, tmp_path, caplog):
    pdf_path = tmp_path / "retryable.pdf"
    _write_image_only_pdf(pdf_path)
    calls = []

    def failing(image, *, rotation=0):
        calls.append(image.size)
        raise RuntimeError("private document text must not enter logs")

    first = extract(
        pdf_path, ocr_backend=CallableOCRBackend(failing), cache=ExtractCache(cache_dir)
    )
    assert first.coverage.pages_unreadable == 1
    assert first.spans == []
    second = extract(
        pdf_path,
        ocr_backend=CallableOCRBackend(lambda image, rotation=0: "recovered after failure"),
        cache=ExtractCache(cache_dir),
    )
    assert calls
    assert second.coverage.pages_recognized == 1
    assert second.coverage.pages_unreadable == 0
    assert [span.text for span in second.spans] == ["recovered after failure"]
    assert "page 1" in caplog.text and "RuntimeError" in caplog.text
    assert "private document text" not in caplog.text
