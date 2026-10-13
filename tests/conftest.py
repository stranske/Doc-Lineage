"""Shared optional-Docling stub; production adapter and ingest stay real."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest


@pytest.fixture
def docling_items(monkeypatch: pytest.MonkeyPatch) -> Callable[[Sequence[tuple[int, str]]], None]:
    """Install a converter with explicit text-item/page provenance, without model downloads."""

    def install(items: Sequence[tuple[int, str]]) -> None:
        class Document:
            pages = {page: object() for page, _text in items}
            num_pages = max(pages, default=0)

            def iterate_items(self) -> list[tuple[types.SimpleNamespace, int]]:
                return [
                    (
                        types.SimpleNamespace(
                            text=text, prov=[types.SimpleNamespace(page_no=page)]
                        ),
                        0,
                    )
                    for page, text in items
                ]

        class Converter:
            def convert(self, source: str) -> types.SimpleNamespace:
                # Verify that the adapter supplies its immutable input snapshot.
                assert Path(source).read_bytes().startswith(b"%PDF")
                return types.SimpleNamespace(document=Document())

        converter = types.ModuleType("docling.document_converter")
        converter.DocumentConverter = Converter  # type: ignore[attr-defined]
        exceptions = types.ModuleType("docling.exceptions")
        exceptions.ConversionError = RuntimeError  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "docling", types.ModuleType("docling"))
        monkeypatch.setitem(sys.modules, "docling.document_converter", converter)
        monkeypatch.setitem(sys.modules, "docling.exceptions", exceptions)

    return install
