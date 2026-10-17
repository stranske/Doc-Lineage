"""Actual CLI journeys over coexisting PDF/DOCX IDs and fee extraction."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from tests.export.test_docx_redline_golden import NS, _docx, _visible_text

    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(*args: str, expected: int = 0):
        argv = [sys.executable, "-m", "doc_lineage.cli", *args]
        result = subprocess.run(
            argv,
            cwd=work,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
        )
        commands.append(
            {
                "argv": argv,
                "cwd": str(work),
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        (work / "argv-results.json").write_text(json.dumps(commands, indent=2))
        assert result.returncode == expected, result.stderr
        if expected:
            assert result.stdout == ""
        return result

    left, right = work / "a.docx", work / "b.docx"
    left.write_bytes(_docx("The fee is five dollars."))
    right.write_bytes(_docx("The fee is ten dollars."))
    source = ROOT / "tests/fixtures/synthetic_lpa.pdf"
    (work / "before.pdf").write_bytes(source.read_bytes())
    (work / "after.pdf").write_bytes(
        source.read_bytes().replace(b"MANAGEMENT FEE", b"DIFFERENT FEE!")
    )
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (left, right, work / "before.pdf", work / "after.pdf")
    }
    (work / "source-hashes.json").write_text(json.dumps(hashes, indent=2))
    assert hashes["before.pdf"] != hashes["after.pdf"]
    docx_id = run(
        "create-comparison",
        "--original",
        str(left),
        "--modified",
        str(right),
        "--comparison-store",
        "store",
    ).stdout.strip()
    for role in ("before", "after"):
        run("ingest", role + ".pdf", "--output", role, "--no-docling", "--no-ocr")
    pdf_id = run("pair-sections", "before", "after", "--store", "store").stdout.strip()
    records = {p: p.read_bytes() for p in (work / "store").iterdir()}
    pdf = json.loads(run("lookup-section-pairing", pdf_id, "--store", "store").stdout)
    assert pdf["decisions"] and pdf["identity"]["original"]["source_sha256"] == hashes["before.pdf"]
    assert pdf["identity"]["modified"]["source_sha256"] == hashes["after.pdf"]
    run("lookup-section-pairing", docx_id, "--store", "store", expected=1)
    run(
        "export-docx",
        "--blackline",
        pdf_id,
        "--comparison-store",
        "store",
        "--output",
        "wrong.docx",
        expected=1,
    )
    assert not (work / "wrong.docx").exists()
    run(
        "export-docx",
        "--blackline",
        docx_id,
        "--comparison-store",
        "store",
        "--output",
        "redline.docx",
        "--author",
        "Counsel",
    )
    with ZipFile(work / "redline.docx") as package:
        xml = package.read("word/document.xml")
        (work / "redline-document.xml").write_bytes(xml)
        doc = ET.fromstring(xml)
        assert doc.findall(".//w:ins", NS) and doc.findall(".//w:del", NS)
        assert _visible_text(doc, "ins") == "The fee is five dollars."
        assert _visible_text(doc, "del") == "The fee is ten dollars."
    run(
        "extract-variables",
        "before",
        "--source",
        "before.pdf",
        "--entity-ref",
        "fund:alpha_opportunities_iv",
        "--output",
        "extraction",
    )
    variables = json.loads((work / "extraction/tracked-variables.json").read_text())
    assert variables and variables[0]["document_id"] == "document:" + hashes["before.pdf"]
    assert variables[0]["ontology_key"] == "legal.fees.management_rate"
    run("export-fact-key-map", "extraction/tracked-variables.json", "--output", "fact-map")
    # Source changes and reversed order still fail before publication/output.
    run(
        "lookup-section-pairing",
        pdf_id,
        "--store",
        "store",
        "--original-run",
        "after",
        "--modified-run",
        "before",
        expected=1,
    )
    original_modified_bytes = right.read_bytes()
    right.write_bytes(_docx("A changed valid document."))
    run(
        "export-docx",
        "--blackline",
        docx_id,
        "--comparison-store",
        "store",
        "--output",
        "must-not-exist.docx",
        expected=1,
    )
    assert not (work / "must-not-exist.docx").exists()
    right.write_bytes(original_modified_bytes)
    for path, payload in records.items():
        assert path.read_bytes() == payload
    assert all(hashlib.sha256((work / n).read_bytes()).hexdigest() == h for n, h in hashes.items())
    (work / "result.json").write_text(
        json.dumps(
            {
                "docx_id": docx_id,
                "pdf_id": pdf_id,
                "variables": len(variables),
                "native_revisions": "five deleted / ten inserted",
                "immutable_records": True,
            },
            indent=2,
        )
    )
    print("PASS combined real CLI/native/PDF/extraction/hash/immutable contracts")


if __name__ == "__main__":
    main()
