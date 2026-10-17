"""Reconstruct the temporary production disconnection; always restore exact bytes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OLD = b"        parsed = _parse_section_header(segment.text)"
NEW = b"        parsed = None  # ISSUE113_TEMPORARY_PRODUCTION_DISCONNECTION"
NODE = "tests/blackline/test_section_id_pairing.py::test_persisted_pdf_ingest_replays_existing_production_pairing"
EXPECTED = "PERSISTED_INGEST_PAIRING_DISCONNECTED"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run(destination: Path) -> None:
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError("raw artifacts must be outside the checkout")
    destination.mkdir(parents=True, exist_ok=False)
    production = ROOT / "src/doc_lineage/blackline.py"
    test = ROOT / "tests/blackline/test_section_id_pairing.py"
    original, test_bytes = production.read_bytes(), test.read_bytes()
    if original.count(OLD) != 1:
        raise ValueError("expected exactly one original parser call")
    mutated = original.replace(OLD, NEW)
    receipts = []

    def execute(label: str) -> subprocess.CompletedProcess[str]:
        argv = [sys.executable, "-m", "pytest", NODE, "-q", f"--junitxml={destination}/{label}.xml"]
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        )
        (destination / f"{label}.log").write_text(completed.stdout + completed.stderr)
        receipts.append(
            {
                "label": label,
                "argv": argv,
                "exit_code": completed.returncode,
                "production_sha256": digest(production.read_bytes()),
                "test_sha256": digest(test.read_bytes()),
            }
        )
        return completed

    try:
        production.write_bytes(mutated)
        red = execute("disconnected")
    finally:
        production.write_bytes(original)
    if production.read_bytes() != original or test.read_bytes() != test_bytes:
        raise RuntimeError("exact restoration/test identity failed")
    green = execute("restored")
    receipt = {
        "replace_once": {"old": OLD.decode(), "new": NEW.decode()},
        "production_original_sha256": digest(original),
        "production_mutated_sha256": digest(mutated),
        "production_restored_sha256": digest(production.read_bytes()),
        "test_sha256": digest(test_bytes),
        "runs": receipts,
        "named_assertion": EXPECTED,
        "tests_unchanged": test.read_bytes() == test_bytes,
    }
    (destination / "mutation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if red.returncode != 1 or EXPECTED not in red.stdout or green.returncode != 0:
        raise RuntimeError("expected named AssertionError RED then restored GREEN")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
