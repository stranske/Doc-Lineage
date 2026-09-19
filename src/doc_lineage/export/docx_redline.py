"""Export native Word tracked changes using python-redlines."""

from typing import cast


def export_docx_redline(original: bytes, modified: bytes, *, author: str = "Doc-Lineage") -> bytes:
    """Compare two DOCX packages and return a DOCX containing tracked changes.

    ``original`` is the baseline and ``modified`` is the revised document.
    Revisions are attributed to ``author``. The bundled Docxodus engine runs
    locally; its dependency, invalid-document, and comparison errors propagate
    to the caller. Neither input is modified.
    """
    if not author.strip():
        raise ValueError("Tracked changes require a non-empty author")

    from python_redlines import DocxodusEngine

    redline, _, _ = DocxodusEngine().run_redline(author, original, modified)
    return cast(bytes, redline)
