"""Current-main control after #128 merged: actual public PDF-to-claim-to-map calls."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from doc_lineage.extract.variables import validate

TIMEOUT_SECONDS = 300

ROOT = Path(__file__).resolve().parents[3]


def run(destination: Path) -> None:
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError("raw artifacts must be outside the checkout")
    destination.mkdir(parents=True, exist_ok=False)
    source = ROOT / "tests/fixtures/synthetic_lpa.pdf"
    commands = [
        [
            "ingest",
            str(source),
            "--output",
            str(destination / "ingest"),
            "--no-docling",
            "--no-ocr",
        ],
        [
            "extract-variables",
            str(destination / "ingest"),
            "--source",
            str(source),
            "--entity-ref",
            "fund:synthetic_alpha",
            "--output",
            str(destination / "claims"),
        ],
        [
            "export-fact-key-map",
            str(destination / "claims/tracked-variables.json"),
            "--output",
            str(destination / "map"),
        ],
    ]
    receipts = []
    for args in commands:
        argv = [sys.executable, "-m", "doc_lineage.cli", *args]
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as exc:

            def text(value: str | bytes | None) -> str:
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""

            receipts.append(
                {
                    "argv": argv,
                    "exit_code": None,
                    "status": "timeout",
                    "timeout_seconds": TIMEOUT_SECONDS,
                    "stdout": text(exc.stdout),
                    "stderr": text(exc.stderr),
                }
            )
            (destination / "commands.json").write_text(json.dumps(receipts, indent=2) + "\n")
            raise RuntimeError(f"command timed out after {TIMEOUT_SECONDS}s: {argv}") from exc
        receipts.append(
            {
                "argv": argv,
                "exit_code": completed.returncode,
                "status": "passed" if completed.returncode == 0 else "failed",
                "timeout_seconds": TIMEOUT_SECONDS,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        (destination / "commands.json").write_text(json.dumps(receipts, indent=2) + "\n")
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
    records = json.loads((destination / "claims/tracked-variables.json").read_text())
    assert len(records) == 1
    (record,) = records
    validate("tracked-variable-v1", record)
    assert record["ontology_key"] == "legal.fees.management_rate"
    assert record["entity_ref"] == "fund:synthetic_alpha"
    assert [s["rate"] for s in record["value_structured"]["schedule"]] == [1.75, 1.25]
    evidence = record["evidence"]
    assert evidence["source_id"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert evidence == json.loads((destination / "claims" / record["evidence_ref"]).read_text())
    assert evidence["locator"]["page"] == 0
    mapping = json.loads((destination / "map/fact_key_map.json").read_text())
    assert mapping[record["variable_id"]] == {
        "ontology_key": record["ontology_key"],
        "entity_ref": record["entity_ref"],
    }
    for name in ("ingest", "claims", "map"):
        manifest = json.loads((destination / name / "artifact-manifest.json").read_text())
        for artifact in manifest["artifacts"]:
            raw = (destination / name / artifact["path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
            assert len(raw) == artifact["bytes"]
    print("CURRENT_MAIN_LEGAL_HANDOFF: source/claim/evidence/manifest/map bindings pass")


if __name__ == "__main__":
    run(Path(sys.argv[1]))
