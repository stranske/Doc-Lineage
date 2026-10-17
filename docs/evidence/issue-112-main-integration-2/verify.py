"""Verify separate implementation, current evidence, and historical components."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_bytes(revision, path):
    return subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT)


def main():
    for line in (HERE / "SHA256SUMS").read_text().splitlines():
        sha, relative = line.split("  ", 1)
        assert digest(HERE / relative) == sha, relative
    binding = json.loads((HERE / "source-bindings.json").read_text())
    revision = binding["implementation_revision"]
    for path, sha in binding["tracked"].items():
        assert hashlib.sha256(git_bytes(revision, path)).hexdigest() == sha, path
        assert digest(ROOT / path) == sha, path
    for path, sha in binding["generated_non_git_build_metadata"].items():
        assert digest(HERE / "generated-build-metadata" / path) == sha, path

    def verify_outputs(receipt):
        for path, sha in receipt["outputs"].items():
            assert digest(HERE / path) == sha, path

    for label in [
        "focused",
        "full",
        "ruff",
        "black",
        "mypy-focused",
        "combined-replay",
        "real-pdf-replay",
    ]:
        receipt = json.loads((HERE / f"{label}.json").read_text())
        assert receipt["exit_code"] == 0 and receipt["bindings_unchanged"], label
        assert receipt["git_revision"] == revision, label
        for path, sha in receipt["bindings"].items():
            assert (binding["tracked"] | binding["generated_non_git_build_metadata"])[
                path
            ] == sha, path
        verify_outputs(receipt)
    for label, total in [("focused", 282), ("full", 625)]:
        tree = ET.parse(HERE / f"{label}.xml").getroot()
        assert len(list(tree.iter("testcase"))) == total
        assert not any(list(tree.iter(tag)) for tag in ["failure", "error", "skipped"])
    proofs = json.loads((HERE / "causal-proof.json").read_text())
    assert len(proofs) == 8
    for proof in proofs:
        name = proof["variant"]
        assert digest(ROOT / proof["path"]) == proof["source_green_sha256"]
        assert digest(HERE / f"{name}.green.py.txt") == proof["source_green_sha256"]
        assert digest(HERE / f"{name}.red.py.txt") == proof["source_red_sha256"]
        assert proof["source_green_sha256"] != proof["source_red_sha256"]
        assert proof["byte_identical_restoration"]
        for path, sha in proof["unchanged_test_hashes"].items():
            assert digest(ROOT / path) == sha, path
        for state, exit_code in [("red", 1), ("restored-green", 0)]:
            receipt = json.loads((HERE / f"{name}-{state}.json").read_text())
            assert receipt["exit_code"] == exit_code and receipt["bindings_unchanged"]
            verify_outputs(receipt)
            tree = ET.parse(HERE / f"{name}-{state}.xml").getroot()
            assert len(list(tree.iter("testcase"))) == 1
            assert len(list(tree.iter("failure"))) == exit_code
            assert not list(tree.iter("error")) and not list(tree.iter("skipped"))
        assert proof["assertion"] in (HERE / f"{name}-red.log").read_text()
    records = list((HERE / "native").glob("*/result.json"))
    assert len(records) == 34
    for path in records:
        data = json.loads(path.read_text())
        assert (
            data["returncode"] == 0
            and data["sha256"] == "12b0955111e348543e55ac9fbc06599b3e79294781198c6fb1b46f3029867c36"
        )
        assert data["argv"][0] == data["path"]
        for role in ["original", "modified", "output"]:
            docx = path.parent / f"{role}.docx"
            assert digest(docx) == data[f"{role}_sha256"]
            with ZipFile(docx) as package:
                assert (
                    package.read("word/document.xml")
                    == (path.parent / f"{role}-document.xml").read_bytes()
                )
    history = json.loads((HERE / "historical-preservation.json").read_text())
    for _folder, item in history["historical_bundles"].items():
        for path, sha in item["files"].items():
            assert digest(ROOT / path) == sha, path
            assert hashlib.sha256(git_bytes(item["revision"], path)).hexdigest() == sha, path
    old = "5b6c5042da6182c14cdf65d5997db2bb180157ca"
    oldbindings = json.loads(
        git_bytes(old, "docs/evidence/issue-112-review-recovery/source-bindings.json")
    )
    generated = {
        r["path"] for r in history["historical_binding_disposition"]["untracked_build_metadata"]
    }
    assert len(generated) == 6
    for path, sha in oldbindings.items():
        if path not in generated:
            assert hashlib.sha256(git_bytes(old, path)).hexdigest() == sha, path
    for label in ["mypy-full", "mypy-main-baseline"]:
        receipt = json.loads((HERE / f"{label}.json").read_text())
        assert receipt["exit_code"] == 1 and receipt["bindings_unchanged"]
        log = (HERE / f"{label}.log").read_text()
        assert log.count("error:") == 2
        assert ':111: error: Unused "type: ignore"' in log
        assert ':112: error: Unused "type: ignore"' in log
        verify_outputs(receipt)
    print(
        "PASS: current revision and separate historical tracked bindings; real XML/causal/native evidence. Six historical generated metadata files remain unavailable from Git."
    )


if __name__ == "__main__":
    main()
