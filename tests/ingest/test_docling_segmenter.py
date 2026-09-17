"""Backend selection and offline text recovery in the Docling adapter."""

from __future__ import annotations

import sys
import types
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from doc_lineage.adapters import DOCLING_BACKEND, OFFLINE_BACKEND, segment_document
from doc_lineage.adapters.docling_segmenter import _decode_pdf_string

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_lpa.pdf"


def _pdf_with_pages(*streams: tuple[bytes, bytes]) -> bytes:
    """Build a minimal PDF whose pages reference the given (header_extra, body) streams."""
    out = bytearray(b"%PDF-1.4\n")
    number = 1
    for header_extra, body in streams:
        contents_num, page_num = number, number + 1
        number += 2
        out += (
            f"{contents_num} 0 obj\n<< /Length {len(body)} ".encode("ascii")
            + header_extra
            + b">>\nstream\n"
            + body
            + b"\nendstream\nendobj\n"
        )
        out += (
            f"{page_num} 0 obj\n<< /Type /Page /Parent 99 0 R "
            f"/Contents {contents_num} 0 R >>\nendobj\n".encode("ascii")
        )
    out += b"%%EOF\n"
    return bytes(out)


def _pdf_with_stream(body: bytes, *, header_extra: bytes = b"") -> bytes:
    return _pdf_with_pages((header_extra, body))


def test_plain_text_input_requires_docling(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("alpha lpa v1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="non-PDF input requires Docling"):
        segment_document(source, allow_docling=False)


def test_empty_non_pdf_input_requires_docling(tmp_path: Path) -> None:
    source = tmp_path / "empty.txt"
    source.write_bytes(b"")

    with pytest.raises(ValueError, match="non-PDF input requires Docling"):
        segment_document(source, allow_docling=False)


def test_flate_encoded_stream_is_inflated(tmp_path: Path) -> None:
    body = zlib.compress(b"BT (Compressed clause) Tj ET\n")
    source = tmp_path / "flate.pdf"
    source.write_bytes(_pdf_with_stream(body, header_extra=b"/Filter /FlateDecode "))

    result = segment_document(source, allow_docling=False)

    assert [page.text for page in result.pages] == ["Compressed clause"]


def test_corrupt_flate_stream_is_skipped_not_guessed(tmp_path: Path) -> None:
    source = tmp_path / "broken.pdf"
    source.write_bytes(_pdf_with_stream(b"(Not Tj deflate)", header_extra=b"/Filter /FlateDecode "))

    result = segment_document(source, allow_docling=False)

    assert result.pages_without_text_layer == (1,)


def test_unknown_filter_is_skipped_not_guessed(tmp_path: Path) -> None:
    source = tmp_path / "dct.pdf"
    source.write_bytes(_pdf_with_stream(b"(Scanned) Tj", header_extra=b"/Filter /DCTDecode "))

    result = segment_document(source, allow_docling=False)

    assert result.pages_without_text_layer == (1,)


def test_stream_without_show_operators_is_ignored(tmp_path: Path) -> None:
    source = tmp_path / "graphics.pdf"
    source.write_bytes(_pdf_with_stream(b"0 0 612 792 re f\n"))

    result = segment_document(source, allow_docling=False)

    assert result.pages_without_text_layer == (1,)


def test_trailing_text_without_a_line_break_is_kept(tmp_path: Path) -> None:
    source = tmp_path / "tail.pdf"
    source.write_bytes(_pdf_with_stream(b"BT (First) Tj T* (Second) Tj ET"))

    result = segment_document(source, allow_docling=False)

    assert result.pages[0].text == "First\nSecond"


def test_tj_array_with_kerning_adjustments(tmp_path: Path) -> None:
    source = tmp_path / "tj.pdf"
    source.write_bytes(_pdf_with_stream(b"BT [(First) 20 (Second)] TJ ET"))

    result = segment_document(source, allow_docling=False)

    assert result.pages[0].text == "FirstSecond"


def test_balanced_parentheses_inside_literal_strings(tmp_path: Path) -> None:
    source = tmp_path / "nested.pdf"
    source.write_bytes(_pdf_with_stream(b"BT (Section (A)) Tj ET"))

    result = segment_document(source, allow_docling=False)

    assert result.pages[0].text == "Section (A)"


def test_catalog_pages_reference_is_resolved_when_metadata_precedes_it(tmp_path: Path) -> None:
    source = tmp_path / "catalog.pdf"
    source.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Metadata 9 0 R /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 24 >>\nstream\nBT (Catalog page) Tj ET\nendstream\nendobj\n"
        b"9 0 obj\n<< /Subtype /XML >>\nendobj\n"
        b"xref\n0 10\n0000000000 65535 f \n"
        b"trailer\n<< /Root 1 0 R >>\nstartxref\n0\n%%EOF\n"
    )

    result = segment_document(source, allow_docling=False)

    assert result.pages[0].text == "Catalog page"


def test_pdf_string_escapes_are_resolved() -> None:
    assert _decode_pdf_string(rb"Fee \(1.75\%\)") == "Fee (1.75%)"
    assert _decode_pdf_string(rb"line\nbreak") == "line\nbreak"
    assert _decode_pdf_string(rb"back\\slash") == "back\\slash"
    assert _decode_pdf_string(rb"\101\102") == "AB"
    assert _decode_pdf_string(rb"\q") == "q"
    assert _decode_pdf_string(rb"\8") == "8"
    assert _decode_pdf_string(rb"trailing\\") == "trailing\\"


def test_docling_is_used_when_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stub Docling proves the adapter prefers it and labels the backend honestly."""

    @dataclass
    class _Prov:
        page_no: int

    @dataclass
    class _Item:
        text: str
        prov: tuple[_Prov, ...]

    class _Document:
        num_pages = 3

        def iterate_items(self) -> list[tuple[_Item, int]]:
            return [
                (_Item("Docling clause one", (_Prov(1),)), 0),
                (_Item("   ", (_Prov(1),)), 0),
            ]

    class _Converter:
        def convert(self, _source: str) -> Any:
            return types.SimpleNamespace(document=_Document())

    module = types.ModuleType("docling")
    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = _Converter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docling", module)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    result = segment_document(FIXTURE)

    assert result.backend == DOCLING_BACKEND
    assert [page.page for page in result.pages] == [1, 2, 3]
    assert result.pages[0].text == "Docling clause one"
    assert result.pages[1].text == ""
    assert result.pages[2].text == ""
    assert result.pages_without_text_layer == (2, 3)


def test_docling_returning_nothing_falls_back_to_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Document:
        def iterate_items(self) -> list[tuple[object, int]]:
            return []

    class _Converter:
        def convert(self, _source: str) -> Any:
            return types.SimpleNamespace(document=_Document())

    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = _Converter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docling", types.ModuleType("docling"))
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    result = segment_document(FIXTURE)

    assert result.backend == OFFLINE_BACKEND
    assert len(result.pages) == 2


def test_missing_docling_falls_back_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "docling.document_converter", None)

    result = segment_document(FIXTURE)

    assert result.backend == OFFLINE_BACKEND


def test_docling_convert_failure_falls_back_to_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Converter:
        def convert(self, _source: str) -> Any:
            raise RuntimeError("docling conversion failed")

    converter_module = types.ModuleType("docling.document_converter")
    converter_module.DocumentConverter = _Converter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "docling", types.ModuleType("docling"))
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_module)

    result = segment_document(FIXTURE)

    assert result.backend == OFFLINE_BACKEND
    assert len(result.pages) == 2


def test_segment_document_uses_supplied_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "snapshot.pdf"
    payload = _pdf_with_stream(b"BT (Snapshot clause) Tj ET")
    source.write_bytes(payload)

    result = segment_document(source, allow_docling=False, data=payload)

    assert result.pages[0].text == "Snapshot clause"


def test_a_page_with_no_readable_text_is_still_reported_as_a_page(tmp_path: Path) -> None:
    """The mixed case: a text-less page must not vanish from the page list."""
    source = tmp_path / "mixed.pdf"
    source.write_bytes(
        _pdf_with_pages(
            (b"", b"BT (Readable clause) Tj ET"),
            (b"/Filter /DCTDecode ", b"scanned-image-bytes"),
        )
    )

    result = segment_document(source, allow_docling=False)

    assert [page.page for page in result.pages] == [1, 2]
    assert result.pages[0].text == "Readable clause"
    assert result.pages_without_text_layer == (2,)


def test_page_without_contents_has_no_text_layer(tmp_path: Path) -> None:
    source = tmp_path / "bare.pdf"
    source.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page /Parent 99 0 R >>\nendobj\n%%EOF\n")

    result = segment_document(source, allow_docling=False)

    assert result.pages_without_text_layer == (1,)


def test_dangling_contents_reference_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "dangling.pdf"
    source.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Page /Contents [7 0 R] >>\nendobj\n%%EOF\n")

    result = segment_document(source, allow_docling=False)

    assert result.pages_without_text_layer == (1,)


def test_contents_object_without_a_stream_is_skipped(tmp_path: Path) -> None:
    source = tmp_path / "nostream.pdf"
    source.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<< /Nothing true >>\nendobj\n"
        b"2 0 obj\n<< /Type /Page /Contents 1 0 R >>\nendobj\n%%EOF\n"
    )

    result = segment_document(source, allow_docling=False)

    assert result.pages_without_text_layer == (1,)
