"""The integrated CLI retains distinct PDF and native DOCX ID contracts."""

import json
from pathlib import Path

from tests.export.test_docx_redline_golden import _docx

from doc_lineage import blackline
from doc_lineage.cli import main
from doc_lineage.ingest import ingest_document


def test_combined_cli_keeps_both_comparison_schemas(tmp_path, capsys):
    original, modified = tmp_path / "a.docx", tmp_path / "b.docx"
    original.write_bytes(_docx("The fee is five dollars."))
    modified.write_bytes(_docx("The fee is ten dollars."))
    store = tmp_path / "comparisons"
    assert (
        main(
            [
                "create-comparison",
                "--original",
                str(original),
                "--modified",
                str(modified),
                "--comparison-store",
                str(store),
            ]
        )
        == 0
    ), "DOCX_CREATION_DISPATCH_SURVIVES_INTEGRATION"
    docx_id = capsys.readouterr().out.strip()
    pdf = Path(__file__).resolve().parents[1] / "fixtures/synthetic_lpa.pdf"
    changed = tmp_path / "changed.pdf"
    changed.write_bytes(pdf.read_bytes().replace(b"MANAGEMENT FEE", b"DIFFERENT FEE!"))
    left, right = tmp_path / "left", tmp_path / "right"
    for source, run in [(pdf, left), (changed, right)]:
        ingest_document(source, output_dir=run, allow_docling=False)
    assert (
        main(["pair-sections", str(left), str(right), "--store", str(store)]) == 0
    ), "PDF_PAIRING_DISPATCH_SURVIVES_INTEGRATION"
    pdf_id = capsys.readouterr().out.strip()
    before = {path: path.read_bytes() for path in store.iterdir()}
    assert docx_id != pdf_id
    assert blackline.load_comparison_record(docx_id, store=store).original_path == original
    assert main(["lookup-section-pairing", pdf_id, "--store", str(store)]) == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["schema_version"] == "section-pairing-comparison/v1"
    assert replay["decisions"], "PDF_PAIRING_DECISIONS_SURVIVE_INTEGRATION"
    assert (
        main(["lookup-section-pairing", docx_id, "--store", str(store)]) == 1
    ), "SECTION_LOADER_REJECTS_DOCX_SCHEMA"
    assert capsys.readouterr().out == ""
    output = tmp_path / "not-pdf.docx"
    assert (
        main(
            [
                "export-docx",
                "--blackline",
                pdf_id,
                "--comparison-store",
                str(store),
                "--output",
                str(output),
            ]
        )
        == 1
    ), "DOCX_LOADER_REJECTS_SECTION_SCHEMA"
    assert capsys.readouterr().out == ""
    assert not output.exists()
    assert all(path.read_bytes() == payload for path, payload in before.items())
