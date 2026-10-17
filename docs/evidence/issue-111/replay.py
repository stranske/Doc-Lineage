"""Replay offline source-to-claim acceptance into a NEW --output directory.

Requires the project's development dependencies (including reportlab).
Run with your selected Python: python docs/evidence/issue-111/replay.py --output /tmp/new-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "src"))
    from doc_lineage.extract.variables import validate

    args.output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONPATH": str(repo / "src")}

    def cli(*parts: str, expected: int = 0) -> None:
        argv = [sys.executable, "-m", "doc_lineage.cli", *parts]
        print(json.dumps({"argv": argv}), flush=True)
        result = subprocess.run(argv, cwd=repo, env=env, check=False)
        assert result.returncode == expected, argv

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    baseline = repo / "tests/fixtures/synthetic_lpa.pdf"
    for name in ("baseline", "changed", "ambiguous"):
        work = args.output / name
        work.mkdir()
        if name == "baseline":
            source = baseline
        else:
            from reportlab.pdfgen import canvas

            fixture = repo / "tests/fixtures/mutations/management_fee_bump/after_segments.json"
            source = work / "control.pdf"
            pdf = canvas.Canvas(str(source), invariant=1)
            page, y = 1, 750
            for segment in json.loads(fixture.read_text())["segments"]:
                if page != segment["page"]:
                    pdf.showPage()
                    page, y = segment["page"], 750
                text = segment["text"]
                if name == "ambiguous" and "MANAGEMENT FEE" in text:
                    text = text.replace("2.0%", "2.0% or 3.0%")
                for line in textwrap.wrap(text, 88):
                    pdf.drawString(40, y, line)
                    y -= 15
                y -= 15
            pdf.save()
        ingest, extracted, mapping = (work / p for p in ("ingest", "extract", "map"))
        cli("ingest", str(source), "--no-docling", "--no-ocr", "--output", str(ingest))
        cli(
            "extract-variables",
            str(ingest),
            "--source",
            str(source),
            "--entity-ref",
            "fund:alpha_iv",
            "--output",
            str(extracted),
        )
        records_path = extracted / "tracked-variables.json"
        records = json.loads(records_path.read_text())
        unresolved = json.loads((extracted / "unresolved.json").read_text())
        if name == "ambiguous":
            assert records == [] and unresolved[0]["status"] == "unresolved"
            assert "value_structured" not in unresolved[0] and "value_text" not in unresolved[0]
            cli("export-fact-key-map", str(records_path), "--output", str(mapping), expected=1)
            assert not mapping.exists()
        else:
            (record,) = records
            assert not unresolved
            validate("tracked-variable-v1", record)
            validate("evidence-object-v1", record["evidence"])
            assert record["value_structured"]["schedule"][0]["rate"] == (
                1.75 if name == "baseline" else 2.0
            )
            assert record["value_structured"]["schedule"][1]["rate"] == 1.25
            assert record["value_text"] in record["evidence"]["excerpt"]
            assert record["evidence"]["source_id"] == digest(source)
            assert record["evidence"]["locator"]["page"] == 0
            assert (
                json.loads((extracted / record["evidence_ref"]).read_text()) == record["evidence"]
            )
            assert (
                extracted / record["provenance"]["mirror"]["blob_path"]
            ).read_bytes() == source.read_bytes()
            cli("export-fact-key-map", str(records_path), "--output", str(mapping))
            assert json.loads((mapping / "fact_key_map.json").read_text())[
                record["variable_id"]
            ] == {"ontology_key": "legal.fees.management_rate", "entity_ref": "fund:alpha_iv"}
        for stage in (ingest, extracted) + (() if name == "ambiguous" else (mapping,)):
            manifest = json.loads((stage / "artifact-manifest.json").read_text())
            validate("artifact-manifest-v1", manifest)
            for artifact in manifest["artifacts"]:
                path = stage / artifact["path"]
                assert digest(path) == artifact["sha256"]
                assert path.stat().st_size == artifact["bytes"]
    print(
        "OFFLINE_ACCEPTANCE_PASS: actual PDF -> persisted ingest -> claims/evidence -> fact map; changed/ambiguous controls"
    )


if __name__ == "__main__":
    main()
