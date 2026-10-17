"""Verify portable evidence, real JUnit cases and immutable historical bindings."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
# The continuation changed the regression after these genuine runs. Never rebind
# historical XML/mutation proof to today's test bytes.
HISTORICAL_REVISION = "a9e5ce23c4295a1948f6f7bd58ea50fcddd67521"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or not name or name != relative.as_posix():
        raise ValueError(f"invalid evidence path: {name!r}")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"evidence path escapes directory: {name!r}")
    return path


def verify_checksums(directory: Path) -> None:
    entries: dict[str, str] = {}
    for number, line in enumerate((directory / "SHA256SUMS").read_text().splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line)
        if match is None:
            raise ValueError(f"malformed SHA256SUMS line {number}")
        expected, name = match.groups()
        path = contained(directory, name)
        if name == "SHA256SUMS":
            raise ValueError("SHA256SUMS must exclude itself")
        if name in entries:
            raise ValueError(f"duplicate checksum entry: {name}")
        entries[name] = expected.lower()
        if not path.is_file():
            raise ValueError(f"checksum entry is not a file: {name}")
        if sha(path) != expected.lower():
            raise ValueError(f"evidence checksum mismatch: {name}")
    inventory = set()
    for path in directory.rglob("*"):
        name = path.relative_to(directory).as_posix()
        contained(directory, name)  # Reject escaping symlinks even when unlisted.
        if path.is_file() and name != "SHA256SUMS":
            inventory.add(name)
    if set(entries) != inventory:
        raise ValueError(
            f"checksum inventory mismatch: unlisted={sorted(inventory - entries.keys())}, "
            f"extra={sorted(entries.keys() - inventory)}"
        )


def validate_junit(path: Path, tests: int, failures: int = 0) -> None:
    root = ET.parse(path).getroot()
    if root.tag not in ("testsuite", "testsuites"):
        raise ValueError(f"missing testsuite: {path}")
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError(f"missing testsuite: {path}")

    def counts(suite: ET.Element) -> tuple[int, int, int, int]:
        cases = list(suite.findall("testcase"))
        actual = (
            len(cases),
            sum(len(case.findall("failure")) for case in cases),
            sum(len(case.findall("error")) for case in cases) + len(suite.findall("error")),
            sum(len(case.findall("skipped")) for case in cases),
        )
        for child in suite.findall("testsuite"):
            nested = counts(child)
            actual = (
                actual[0] + nested[0],
                actual[1] + nested[1],
                actual[2] + nested[2],
                actual[3] + nested[3],
            )
        try:
            declared = tuple(
                int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"missing/invalid JUnit counts: {path}") from exc
        if declared != actual:
            raise ValueError(f"JUnit declared/actual mismatch: {path}: {declared} != {actual}")
        return actual

    totals = (0, 0, 0, 0)
    for suite in suites:
        counted = counts(suite)
        totals = (
            totals[0] + counted[0],
            totals[1] + counted[1],
            totals[2] + counted[2],
            totals[3] + counted[3],
        )
    if totals != (tests, failures, 0, 0) or not totals[0]:
        raise ValueError(f"JUnit outcome mismatch: {path}: {totals}")
    if root.tag == "testsuites":
        for key, actual in zip(("tests", "failures", "errors", "skipped"), totals, strict=True):
            if key in root.attrib and int(root.attrib[key]) != actual:
                raise ValueError(f"JUnit aggregate mismatch: {path}: {key}")


def historical_sha(name: str) -> str:
    contained(ROOT, name)
    raw = subprocess.check_output(["git", "show", f"{HISTORICAL_REVISION}:{name}"], cwd=ROOT)
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    verify_checksums(HERE)
    source = json.loads((HERE / "source-hashes.json").read_text())
    for path, expected in source["final_full_bindings"].items():
        if historical_sha(path) != expected:
            raise ValueError(f"historical source/test/fixture binding mismatch: {path}")
    for path, tests, failures in (
        ("final-full.xml", 533, 0),
        ("related.xml", 162, 0),
        ("focused.xml", 11, 0),
        ("final-mutation/disconnected.xml", 1, 1),
        ("final-mutation/restored.xml", 1, 0),
    ):
        validate_junit(HERE / path, tests, failures)
    mutation = json.loads((HERE / "final-mutation/mutation.json").read_text())
    if mutation["production_original_sha256"] != mutation["production_restored_sha256"]:
        raise ValueError("production was not restored exactly")
    if not mutation["tests_unchanged"]:
        raise ValueError("the causally tested regression changed during mutation")
    if historical_sha("tests/blackline/test_section_id_pairing.py") != mutation["test_sha256"]:
        raise ValueError("the historical causally tested regression changed")
    for directory in (
        "final-control/before",
        "final-control/after",
        "current-legal/ingest",
        "current-legal/claims",
        "current-legal/map",
    ):
        manifest = json.loads((HERE / directory / "artifact-manifest.json").read_text())
        for artifact in manifest["artifacts"]:
            path = contained(HERE / directory, artifact["path"])
            if sha(path) != artifact["sha256"] or path.stat().st_size != artifact["bytes"]:
                raise ValueError(f"actual persisted artifact binding mismatch: {path.name}")
    refresh = json.loads((HERE / "recovery/source-bindings.json").read_text())
    for name, expected in refresh["current_inputs"].items():
        if sha(contained(ROOT, name)) != expected:
            raise ValueError(f"current recovery binding mismatch: {name}")
    for entry in refresh["junit"]:
        validate_junit(
            contained(HERE / "recovery", entry["path"]), entry["tests"], entry["failures"]
        )
    current_mutation = json.loads((HERE / "recovery/mutation/mutation.json").read_text())
    if (
        not current_mutation["tests_unchanged"]
        or current_mutation["production_original_sha256"]
        != current_mutation["production_restored_sha256"]
        or sha(ROOT / "tests/blackline/test_section_id_pairing.py")
        != current_mutation["test_sha256"]
        or sha(ROOT / "src/doc_lineage/blackline.py")
        != current_mutation["production_restored_sha256"]
    ):
        raise ValueError("current mutation binding/restoration mismatch")
    print(
        "EVIDENCE_BINDINGS_PASS: exact inventory, historical/current bindings, genuine JUnit/mutation"
    )


if __name__ == "__main__":
    main()
