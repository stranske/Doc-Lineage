"""Docling segmenter wrapper with an offline fallback for CI.

Docling is the intended production segmenter, but it is a heavy optional
dependency that cannot be installed in every CI leg. This adapter therefore
resolves a backend at call time and always reports which one produced the text,
so a caller can never mistake fallback output for a Docling parse. The fallback
reads the PDF's own content streams; it does not fabricate text and it does not
perform recognition. Whether a page carried a text layer at all is reported
separately, because "no extractable text" is a real finding that a recognition
fallback (issue #3) has to act on, not a silence to paper over.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from pathlib import Path

DOCLING_BACKEND = "docling"
OFFLINE_BACKEND = "offline-pdf-text"

PDF_MAGIC = b"%PDF"

_OBJECT_PATTERN = re.compile(rb"(?<![0-9])(\d+)\s+\d+\s+obj\b(.*?)\bendobj", re.DOTALL)
_STREAM_PATTERN = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_PAGE_TYPE_PATTERN = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")
_CONTENTS_PATTERN = re.compile(rb"/Contents\s*(\[[^\]]*\]|\d+\s+\d+\s+R)")
_REFERENCE_PATTERN = re.compile(rb"(\d+)\s+\d+\s+R")
_SHOW_TEXT_PATTERN = re.compile(rb"\((?:\\.|[^()\\])*\)\s*(?:Tj|TJ|'|\")|T\*", re.DOTALL)
_STRING_PATTERN = re.compile(rb"\((?:\\.|[^()\\])*\)", re.DOTALL)
_PDF_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}


@dataclass(frozen=True)
class PageText:
    """Text recovered for one page, with an explicit text-layer verdict."""

    page: int
    text: str
    has_text_layer: bool


@dataclass(frozen=True)
class SegmenterResult:
    """Pages plus the provenance of the backend that produced them."""

    backend: str
    pages: tuple[PageText, ...]

    @property
    def pages_without_text_layer(self) -> tuple[int, ...]:
        return tuple(page.page for page in self.pages if not page.has_text_layer)


def segment_document(path: Path, *, allow_docling: bool = True) -> SegmenterResult:
    """Return per-page text for ``path`` using Docling when it is importable.

    ``allow_docling=False`` forces the offline backend. Tests use it to exercise
    the fallback deterministically on machines where Docling happens to exist.
    """
    data = path.read_bytes()
    if allow_docling:
        docling_pages = _try_docling(path)
        if docling_pages is not None:
            return SegmenterResult(backend=DOCLING_BACKEND, pages=docling_pages)
    return SegmenterResult(backend=OFFLINE_BACKEND, pages=_offline_pages(data))


def _try_docling(path: Path) -> tuple[PageText, ...] | None:
    """Convert with Docling, or return ``None`` when it is unavailable."""
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except ImportError:
        return None

    document = DocumentConverter().convert(str(path)).document
    by_page: dict[int, list[str]] = {}
    for item, _level in document.iterate_items():
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            continue
        for provenance in getattr(item, "prov", ()) or ():
            page_no = int(getattr(provenance, "page_no", 1) or 1)
            by_page.setdefault(page_no, []).append(text)
    if not by_page:
        return None
    return tuple(
        PageText(page=page, text="\n".join(lines), has_text_layer=bool(lines))
        for page, lines in sorted(by_page.items())
    )


def _offline_pages(data: bytes) -> tuple[PageText, ...]:
    """Recover page text without third-party tooling."""
    if not data.startswith(PDF_MAGIC):
        text = data.decode("utf-8", errors="replace").strip()
        return (PageText(page=1, text=text, has_text_layer=bool(text)),)

    objects = _objects(data)
    page_bodies = [body for body in objects.values() if _is_page_object(body)]
    if not page_bodies:
        # A PDF with no page object is empty as far as this backend can tell.
        # Report one page with no text layer rather than returning nothing, so a
        # caller still sees a page and can route recognition. Returning no pages
        # would make "unreadable" indistinguishable from "read, found nothing".
        return (PageText(page=1, text="", has_text_layer=False),)

    pages: list[PageText] = []
    for index, body in enumerate(page_bodies, start=1):
        text = "\n".join(
            extracted
            for extracted in (
                _extract_stream_text(stream) for stream in _page_streams(body, objects)
            )
            if extracted
        ).strip()
        # A page whose content this backend cannot read stays a page. Dropping it
        # would hide the one signal a recognition fallback needs.
        pages.append(PageText(page=index, text=text, has_text_layer=bool(text)))
    return tuple(pages)


def _objects(data: bytes) -> dict[int, bytes]:
    """Return indirect object bodies keyed by object number, in file order."""
    return {int(match.group(1)): match.group(2) for match in _OBJECT_PATTERN.finditer(data)}


def _is_page_object(body: bytes) -> bool:
    """True for ``/Type /Page``; ``/Type /Pages`` is the tree node, not a page."""
    return bool(_PAGE_TYPE_PATTERN.search(body))


def _page_streams(page_body: bytes, objects: dict[int, bytes]) -> list[bytes]:
    """Return the decoded content streams a page references, in order."""
    contents = _CONTENTS_PATTERN.search(page_body)
    if not contents:
        return []
    streams: list[bytes] = []
    for reference in _REFERENCE_PATTERN.finditer(contents.group(1)):
        body = objects.get(int(reference.group(1)))
        if body is None:
            continue
        decoded = _decode_stream(body)
        if decoded is not None:
            streams.append(decoded)
    return streams


def _decode_stream(object_body: bytes) -> bytes | None:
    """Return one object's stream payload, or ``None`` when it cannot be read."""
    match = _STREAM_PATTERN.search(object_body)
    if not match:
        return None
    header = object_body[: match.start()]
    payload = match.group(1)
    if b"/FlateDecode" in header:
        try:
            return zlib.decompress(payload)
        except zlib.error:
            return None
    if b"/Filter" in header:
        # An encoding this backend cannot read is not text it may guess at.
        return None
    return payload


def _extract_stream_text(stream: bytes) -> str:
    """Join the text-showing operators of one content stream into page text."""
    lines: list[str] = []
    current: list[str] = []
    for match in _SHOW_TEXT_PATTERN.finditer(stream):
        token = match.group(0)
        if token == b"T*":
            lines.append("".join(current))
            current = []
            continue
        for string in _STRING_PATTERN.finditer(token):
            current.append(_decode_pdf_string(string.group(0)[1:-1]))
    if current:
        lines.append("".join(current))
    return "\n".join(lines).strip()


def _decode_pdf_string(raw: bytes) -> str:
    """Resolve PDF literal-string escapes into text."""
    out = bytearray()
    index = 0
    while index < len(raw):
        byte = raw[index : index + 1]
        if byte != b"\\":
            out += byte
            index += 1
            continue
        index += 1
        if index >= len(raw):
            break
        escape = raw[index : index + 1]
        if escape in _PDF_ESCAPES:
            out += _PDF_ESCAPES[escape]
            index += 1
            continue
        if escape.isdigit():
            digits = raw[index : index + 3]
            octal = bytes(c for c in digits if 0x30 <= c <= 0x37)
            if octal:
                out.append(int(octal, 8) & 0xFF)
                index += len(octal)
                continue
        out += escape
        index += 1
    return out.decode("latin-1")
