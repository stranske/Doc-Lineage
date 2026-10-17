"""Verify portable evidence, real JUnit cases and immutable historical bindings."""

from __future__ import annotations

import argparse
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
RECOVERY_REVISION = "c27168e94364d52ec681d3b3827281118d46a8ba"
INTEGRATION = HERE.parent / "issue-113-main-integration"
INPUT_PATHS = (
    "src",
    "tests",
    "schemas",
    "vocab",
    "docs/contracts/schemas",
    "docs/evidence/issue-113/deliberate_break.py",
    "docs/evidence/issue-113/probe_base.py",
    "docs/evidence/issue-113/probe_current.py",
    "docs/evidence/issue-113/replay_control.py",
    "docs/evidence/issue-113/replay_legal.py",
    "docs/evidence/issue-113/verify_evidence.py",
    "pyproject.toml",
    "requirements.lock",
    "requirements-dev.lock",
)


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


def historical_sha(name: str, revision: str = HISTORICAL_REVISION) -> str:
    contained(ROOT, name)
    raw = subprocess.check_output(["git", "show", f"{revision}:{name}"], cwd=ROOT)
    return hashlib.sha256(raw).hexdigest()


def verify_revision_inputs(inputs: dict[str, str], revision: str) -> list[str]:
    """Reject corrupt archive bindings; report working-tree drift separately."""
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None or not inputs:
        raise ValueError("nonempty bindings and full immutable revision required")
    drift = []
    for name, expected in inputs.items():
        if historical_sha(name, revision) != expected:
            raise ValueError(f"immutable source/test binding mismatch: {revision}:{name}")
        current = contained(ROOT, name)
        if not current.is_file() or sha(current) != expected:
            drift.append(name)
    return sorted(drift)


def input_inventory(revision: str | None = None) -> set[str]:
    argv = (
        ["git", "ls-tree", "-r", "--name-only", revision, "--"]
        if revision is not None
        else ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--"]
    )
    return set(subprocess.check_output([*argv, *INPUT_PATHS], cwd=ROOT, text=True).splitlines())


def verify_mutation(directory: Path, revision: str) -> None:
    mutation = json.loads((directory / "mutation.json").read_text())
    if (
        not mutation["tests_unchanged"]
        or mutation["production_original_sha256"] != mutation["production_restored_sha256"]
        or historical_sha("tests/blackline/test_section_id_pairing.py", revision)
        != mutation["test_sha256"]
        or historical_sha("src/doc_lineage/blackline.py", revision)
        != mutation["production_restored_sha256"]
    ):
        raise ValueError("immutable mutation binding/restoration mismatch")


def verify_integration(directory: Path) -> list[str]:
    verify_checksums(directory)
    binding = json.loads((directory / "source-bindings.json").read_text())
    revision, inputs = binding["revision"], binding["inputs"]
    drift = verify_revision_inputs(inputs, revision)
    if set(inputs) != input_inventory(revision):
        raise ValueError("integration immutable input inventory mismatch")
    drift = sorted(set(drift) | (input_inventory() ^ set(inputs)))
    for entry in binding["junit"]:
        validate_junit(contained(directory, entry["path"]), entry["tests"], entry["failures"])
    for name in binding["commands"]:
        command = json.loads(contained(directory, name).read_text())
        if command["revision"] != revision or command["bindings"] != inputs:
            raise ValueError(f"integration execution binding mismatch: {name}")
        if sha(contained(directory, command["log"])) != command["log_sha256"]:
            raise ValueError(f"integration execution log mismatch: {name}")
        if command["exit_code"] != 0:
            raise ValueError(f"integration execution failed: {name}")
    verify_mutation(directory / "mutation", revision)
    return drift


def require_current(drift: list[str] | None) -> None:
    if drift is None or drift:
        raise ValueError(f"CURRENT_ADMISSION_FAIL: integration inputs absent or drifted: {drift}")


def main(strict_current: bool = False) -> None:
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
    recovery_drift = verify_revision_inputs(refresh["current_inputs"], RECOVERY_REVISION)
    for entry in refresh["junit"]:
        validate_junit(
            contained(HERE / "recovery", entry["path"]), entry["tests"], entry["failures"]
        )
    verify_mutation(HERE / "recovery/mutation", RECOVERY_REVISION)
    integration_drift = verify_integration(INTEGRATION) if INTEGRATION.exists() else None
    print("ARCHIVE_PASS: exact inventories, immutable bindings, genuine JUnit/mutation")
    print(
        json.dumps(
            {
                "recovery_revision": RECOVERY_REVISION,
                "recovery_current_input_drift": recovery_drift,
                "integration_current_input_drift": integration_drift,
                "current_admission": "MATCH" if integration_drift == [] else "UNQUALIFIED",
            },
            sort_keys=True,
        )
    )
    if strict_current:
        require_current(integration_drift)
        print("CURRENT_ADMISSION_PASS: fresh integration proof matches current inputs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-current",
        action="store_true",
        help="also require fresh integration proof matching current source/test inputs",
    )
    main(parser.parse_args().require_current)
