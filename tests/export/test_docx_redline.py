"""Verify the export boundary independently of the native comparison engine."""

import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from doc_lineage.export import export_docx_redline


@pytest.fixture
def engine(monkeypatch):
    module = ModuleType("python_redlines")
    instance = Mock()
    monkeypatch.setattr(module, "DocxodusEngine", Mock(return_value=instance), raising=False)
    monkeypatch.setitem(sys.modules, "python_redlines", module)
    return instance


@pytest.mark.parametrize("author", ["Counsel", "Doc-Lineage"])
def test_passes_ordered_inputs_and_returns_docx(engine, author):
    engine.run_redline.return_value = (b"redline package", "diagnostic output", "")
    kwargs = {} if author == "Doc-Lineage" else {"author": author}

    result = export_docx_redline(b"original package", b"modified package", **kwargs)

    assert result == b"redline package"
    engine.run_redline.assert_called_once_with(author, b"original package", b"modified package")


def test_comparison_errors_propagate(engine):
    engine.run_redline.side_effect = RuntimeError("Comparison failed")
    with pytest.raises(RuntimeError, match="Comparison failed"):
        export_docx_redline(b"invalid", b"invalid")


@pytest.mark.parametrize("author", ["", "  \n"])
def test_blank_author_rejected(engine, author):
    with pytest.raises(ValueError, match="non-empty author"):
        export_docx_redline(b"original", b"modified", author=author)
    engine.run_redline.assert_not_called()
