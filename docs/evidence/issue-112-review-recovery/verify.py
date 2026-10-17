"""Verify retained review-recovery evidence without rewriting it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    for line in (here / "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        assert digest(here / relative) == expected, relative
    source = json.loads((here / "source-bindings.json").read_text())
    for relative, expected in source.items():
        assert digest(root / relative) == expected, relative
    for label in [
        "focused-final",
        "full-final",
        "ruff-final",
        "black-final",
        "mypy-focused-final",
        "real-pdf-replay",
    ]:
        receipt = json.loads((here / f"{label}.json").read_text())
        assert receipt["exit_code"] == 0 and receipt["bindings_unchanged"], label
        assert all(source[n] == sha for n, sha in receipt["bindings"].items())
        for relative, expected in receipt["outputs"].items():
            assert digest(here / relative) == expected
    for proof in json.loads((here / "causal-proof.json").read_text()):
        name = proof["variant"]
        assert digest(root / proof["path"]) == proof["source_green_sha256"]
        assert all(digest(root / n) == sha for n, sha in proof["unchanged_test_hashes"].items())
        assert proof["byte_identical_restoration"]
        assert proof["assertion"] in (here / f"{name}-red.log").read_text()
        for state, failures in [("red", 1), ("restored-green", 0)]:
            tree = ET.parse(here / f"{name}-{state}.xml").getroot()
            cases = list(tree.iter("testcase"))
            assert len(cases) == 1 and len(list(tree.iter("failure"))) == failures
            assert not list(tree.iter("error")) and not list(tree.iter("skipped"))
            receipt = json.loads((here / f"{name}-{state}.json").read_text())
            assert receipt["exit_code"] == failures
            for relative, expected in receipt["outputs"].items():
                assert digest(here / relative) == expected
    for label in ["focused-final", "full-final"]:
        tree = ET.parse(here / f"{label}.xml").getroot()
        assert not any(list(tree.iter(tag)) for tag in ["failure", "error", "skipped"])
    records = list((here / "native").glob("*/result.json"))
    assert records
    for record in records:
        data = json.loads(record.read_text())
        assert data["returncode"] == 0
        assert data["sha256"] == "12b0955111e348543e55ac9fbc06599b3e79294781198c6fb1b46f3029867c36"
    print(
        "PASS: source/test bindings, raw logs, genuine XML, causal RED/restored GREEN, native receipts"
    )


if __name__ == "__main__":
    main()
