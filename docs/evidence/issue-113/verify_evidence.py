"""Verify portable evidence bytes and the final source/test/fixture binding."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    for line in (HERE / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if sha(HERE / name) != expected:
            raise ValueError(f"evidence checksum mismatch: {name}")
    source = json.loads((HERE / "source-hashes.json").read_text())
    for path, expected in source["final_full_bindings"].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f"source/test/fixture binding mismatch: {path}")
    for path, tests, failures in (
        ("final-full.xml", 533, 0),
        ("related.xml", 162, 0),
        ("focused.xml", 11, 0),
        ("final-mutation/disconnected.xml", 1, 1),
        ("final-mutation/restored.xml", 1, 0),
    ):
        suites = ET.parse(HERE / path).getroot().findall("testsuite")
        if sum(int(s.get("tests", "0")) for s in suites) != tests:
            raise ValueError(f"test count mismatch: {path}")
        if sum(int(s.get("failures", "0")) for s in suites) != failures:
            raise ValueError(f"failure count mismatch: {path}")
    mutation = json.loads((HERE / "final-mutation/mutation.json").read_text())
    if mutation["production_original_sha256"] != mutation["production_restored_sha256"]:
        raise ValueError("production was not restored exactly")
    if sha(ROOT / "tests/blackline/test_section_id_pairing.py") != mutation["test_sha256"]:
        raise ValueError("the causally tested regression changed")
    for directory in (
        "final-control/before",
        "final-control/after",
        "current-legal/ingest",
        "current-legal/claims",
        "current-legal/map",
    ):
        manifest = json.loads((HERE / directory / "artifact-manifest.json").read_text())
        for artifact in manifest["artifacts"]:
            path = HERE / directory / artifact["path"]
            if sha(path) != artifact["sha256"] or path.stat().st_size != artifact["bytes"]:
                raise ValueError(f"actual persisted artifact binding mismatch: {path.name}")
    print(
        "EVIDENCE_BINDINGS_PASS: checksums, source/fixture hashes, real XML, mutation and artifacts"
    )


if __name__ == "__main__":
    main()
