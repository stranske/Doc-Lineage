"""Semantic golden test against the real python-redlines engine (B2-034)."""

from io import BytesIO
from subprocess import CalledProcessError
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from doc_lineage.export import export_docx_redline

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def _docx(text: str) -> bytes:
    """Build a minimal synthetic Word package without binary fixtures."""
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            "</Types>",
        )
        package.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="word/document.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
            "</Relationships>",
        )
        # The pinned Docxodus engine reads StyleDefinitionsPart even for plain
        # paragraphs. Include it just as a Word-created document would.
        package.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="styles.xml" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"/>'
            "</Relationships>",
        )
        package.writestr(
            "word/styles.xml",
            f'<w:styles xmlns:w="{W}">'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/>'
            "</w:style></w:styles>",
        )
        package.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W}"><w:body><w:p><w:r>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t>'
            "</w:r></w:p><w:sectPr/></w:body></w:document>",
        )
    return buffer.getvalue()


@pytest.fixture
def engine_cache(tmp_path, monkeypatch):
    # Exercise a fresh extraction without writing to the developer's home cache.
    # Only redirect cache discovery; comparison still uses the bundled engine.
    monkeypatch.setattr(
        "python_redlines.engines.platformdirs.user_cache_dir",
        lambda appname: str(tmp_path / appname),
    )


def _visible_text(node, rejected_tag):
    """Read the paragraph after accepting or rejecting its text revisions."""
    if node.tag == f"{{{W}}}{rejected_tag}":
        return ""
    if node.tag in {f"{{{W}}}t", f"{{{W}}}delText"}:
        return node.text or ""
    return "".join(_visible_text(child, rejected_tag) for child in node)


def test_tracked_changes_present(engine_cache):
    original = _docx("The fee is five dollars.")
    modified = _docx("The fee is ten dollars.")

    try:
        redline = export_docx_redline(original, modified, author="Counsel")
    except CalledProcessError as error:
        # The engine captures its diagnostics; pytest otherwise shows only the
        # exit code. These inputs are synthetic, so include the native failure.
        error.add_note(f"Docxodus stdout:\n{error.stdout or '(empty)'}")
        error.add_note(f"Docxodus stderr:\n{error.stderr or '(empty)'}")
        raise

    with ZipFile(BytesIO(redline)) as package:
        assert package.testzip() is None
        document = ET.fromstring(package.read("word/document.xml"))

    insertions = document.findall(".//w:ins", NS)
    deletions = document.findall(".//w:del", NS)
    assert insertions, "Expected native Word insertion markup"
    assert deletions, "Expected native Word deletion markup"
    assert "ten" in "".join(
        node.text or "" for ins in insertions for node in ins.findall(".//w:t", NS)
    )
    assert "five" in "".join(
        node.text or "" for deletion in deletions for node in deletion.findall(".//w:delText", NS)
    )
    for revision in insertions + deletions:
        assert revision.get(f"{{{W}}}author") == "Counsel"
        assert revision.get(f"{{{W}}}id") is not None

    # Accepting/rejecting the revisions must recover the corresponding input.
    assert _visible_text(document, "del") == "The fee is ten dollars."
    assert _visible_text(document, "ins") == "The fee is five dollars."


@pytest.mark.parametrize(
    ("original_text", "modified_text", "has_insertions", "has_deletions"),
    [
        ("Counsel approves.", "Counsel approves promptly.", True, False),
        ("Counsel approves promptly.", "Counsel approves.", False, True),
        ("Counsel approves.", "Counsel approves.", False, False),
    ],
    ids=["insertion-only", "deletion-only", "unchanged"],
)
def test_revision_round_trip(
    engine_cache, original_text, modified_text, has_insertions, has_deletions
):
    redline = export_docx_redline(_docx(original_text), _docx(modified_text))

    with ZipFile(BytesIO(redline)) as package:
        assert package.testzip() is None
        document = ET.fromstring(package.read("word/document.xml"))

    insertions = document.findall(".//w:ins", NS)
    deletions = document.findall(".//w:del", NS)
    assert bool(insertions) == has_insertions
    assert bool(deletions) == has_deletions
    for revision in insertions + deletions:
        assert revision.get(f"{{{W}}}author") == "Doc-Lineage"
        assert revision.get(f"{{{W}}}id") is not None
    assert _visible_text(document, "del") == modified_text
    assert _visible_text(document, "ins") == original_text
