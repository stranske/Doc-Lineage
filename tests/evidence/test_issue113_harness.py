"""Rejection controls for the audit harness, using genuine pytest XML fixtures.

Corrupt copies are deliberately invalid evidence, never published passing XML.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

EVIDENCE = Path(__file__).resolve().parents[2] / "docs/evidence/issue-113"


def load(name):
    # Avoid introducing unlisted __pycache__ files into the exact evidence inventory.
    path = EVIDENCE / f"{name}.py"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def checksum_tree(tmp_path):
    (tmp_path / "proof").write_bytes(b"actual bytes")
    digest = hashlib.sha256(b"actual bytes").hexdigest()
    line = f"{digest}  proof\n"
    (tmp_path / "SHA256SUMS").write_text(line)
    return line


def test_checksums_accept_blank_lines_and_exclude_own_index(tmp_path):
    line = checksum_tree(tmp_path)
    (tmp_path / "SHA256SUMS").write_text("\n" + line + "\n  \n")
    load("verify_evidence").verify_checksums(tmp_path)


@pytest.mark.parametrize(
    "damage", ["badhex", "malformed", "duplicate", "unlisted", "missing", "corrupt", "self"]
)
def test_checksum_inventory_rejects_corruption(tmp_path, damage):
    line = checksum_tree(tmp_path)
    index = tmp_path / "SHA256SUMS"
    if damage == "badhex":
        index.write_text("z" * 64 + "  proof\n")
    elif damage == "malformed":
        index.write_text("not-a-checksum\n")
    elif damage == "duplicate":
        index.write_text(line * 2)
    elif damage == "unlisted":
        (tmp_path / "hidden").write_bytes(b"not listed")
    elif damage == "missing":
        (tmp_path / "proof").unlink()
    elif damage == "corrupt":
        (tmp_path / "proof").write_bytes(b"tampered")
    else:
        index.write_text(line + "0" * 64 + "  SHA256SUMS\n")
    with pytest.raises(ValueError):
        load("verify_evidence").verify_checksums(tmp_path)


@pytest.mark.parametrize("escape", ["absolute", "traversal", "symlink", "unlisted_symlink"])
def test_checksum_paths_cannot_escape(tmp_path, escape):
    directory = tmp_path / "evidence"
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside bytes")
    name = {"absolute": str(outside), "traversal": "../outside"}.get(escape, "link")
    if "symlink" in escape:
        (directory / "link").symlink_to(outside)
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    (directory / "SHA256SUMS").write_text(
        "" if escape == "unlisted_symlink" else f"{digest}  {name}\n"
    )
    with pytest.raises(ValueError, match="path"):
        load("verify_evidence").verify_checksums(directory)


def test_real_historical_junit_supports_both_roots(tmp_path):
    verifier = load("verify_evidence")
    verifier.validate_junit(EVIDENCE / "focused.xml", 11)
    root = ET.parse(EVIDENCE / "focused.xml").getroot().find("testsuite")
    target = tmp_path / "single-suite.xml"
    ET.ElementTree(root).write(target)
    verifier.validate_junit(target, 11)


@pytest.mark.parametrize(
    "damage", ["empty", "partial", "error", "skip", "missing_counts", "missing_suite"]
)
def test_junit_rejects_incomplete_or_unsuccessful_real_cases(tmp_path, damage):
    tree = ET.parse(EVIDENCE / "focused.xml")
    suite = tree.getroot().find("testsuite")
    cases = suite.findall("testcase")
    if damage in ("empty", "partial"):
        for case in cases if damage == "empty" else cases[:1]:
            suite.remove(case)
    elif damage in ("error", "skip"):
        tag, count = ("error", "errors") if damage == "error" else ("skipped", "skipped")
        ET.SubElement(cases[0], tag, message="rejection control")
        suite.set(count, "1")
    elif damage == "missing_counts":
        del suite.attrib["errors"]
    else:
        tree.getroot().remove(suite)
    target = tmp_path / "INVALID.xml"
    tree.write(target)
    with pytest.raises(ValueError):
        load("verify_evidence").validate_junit(target, 11)


@pytest.mark.parametrize("exception", [NameError, AttributeError, ImportError, RuntimeError])
def test_probe_tool_defects_propagate(exception):
    def broken():
        raise exception("probe defect")

    with pytest.raises(exception, match="probe defect"):
        load("probe_base").observe("broken probe", broken)


@pytest.mark.parametrize("exception", [TypeError, ValueError, SystemExit])
def test_probe_expected_consumer_errors_are_observations(exception):
    def consumer():
        raise exception("consumer result")

    result = load("probe_base").observe("consumer", consumer)
    assert result["exception"] == exception.__name__
    assert result["message"] == "consumer result"


@pytest.mark.parametrize("missing", [True, False])
def test_missing_base_diagnostic_preserves_cause_and_other_git_errors(
    tmp_path, monkeypatch, missing
):
    probe = load("probe_base")
    error = subprocess.CalledProcessError(
        128,
        ["git"],
        stderr=(
            b"fatal: Not a valid object name base" if missing else b"fatal: not a git repository"
        ),
    )

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(probe.subprocess, "check_output", fail)
    with pytest.raises(ValueError if missing else subprocess.CalledProcessError) as raised:
        probe.run(tmp_path / "out")
    assert raised.value.__cause__ is error if missing else raised.value is error
    if missing:
        assert probe.BASE in str(raised.value)
    assert not (tmp_path / "out").exists()


def test_replay_timeout_retains_successful_prefix_and_failure_argv(tmp_path, monkeypatch):
    replay = load("replay_legal")
    calls = []

    def execute(argv, **kwargs):
        assert kwargs["timeout"] == 300
        calls.append(argv)
        if len(calls) == 1:
            return subprocess.CompletedProcess(argv, 0, "first result", "")
        raise subprocess.TimeoutExpired(
            argv, 300, output=b"partial stdout", stderr=b"partial stderr"
        )

    monkeypatch.setattr(replay.subprocess, "run", execute)
    destination = tmp_path / "timeout"
    with pytest.raises(RuntimeError, match="timed out after 300s"):
        replay.run(destination)
    receipts = json.loads((destination / "commands.json").read_text())
    assert len(receipts) == 2
    assert receipts[0]["stdout"] == "first result"
    assert receipts[0]["status"] == "passed"
    assert receipts[1] == {
        "argv": calls[1],
        "exit_code": None,
        "status": "timeout",
        "timeout_seconds": 300,
        "stdout": "partial stdout",
        "stderr": "partial stderr",
    }


def test_replay_nonzero_exit_is_durable(tmp_path, monkeypatch):
    replay = load("replay_legal")
    monkeypatch.setattr(
        replay.subprocess,
        "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 2, "", "bad child"),
    )
    with pytest.raises(RuntimeError, match="bad child"):
        replay.run(tmp_path / "failed")
    receipt = json.loads((tmp_path / "failed/commands.json").read_text())[0]
    assert receipt["status"] == "failed" and receipt["exit_code"] == 2


@pytest.mark.parametrize("damage", ["red_exit", "red_marker", "green_exit", "green_changes_test"])
def test_invalid_mutation_never_writes_success_receipt(tmp_path, monkeypatch, damage):
    mutation = load("deliberate_break")
    checkout = tmp_path / "checkout"
    production = checkout / "src/doc_lineage/blackline.py"
    production.parent.mkdir(parents=True)
    # This is a subprocess rejection control; actual causal RED/GREEN is replayed separately.
    original = mutation.OLD + b"\n"
    production.write_bytes(original)
    test = checkout / "tests/blackline/test_section_id_pairing.py"
    test.parent.mkdir(parents=True)
    test.write_bytes(b"unchanged test identity")
    monkeypatch.setattr(mutation, "ROOT", checkout)
    calls = []

    def execute(argv, **kwargs):
        calls.append(argv)
        red = len(calls) == 1
        if not red and damage == "green_changes_test":
            test.write_bytes(b"unexpected test edit")
        return subprocess.CompletedProcess(
            argv,
            (0 if damage == "red_exit" else 1) if red else (1 if damage == "green_exit" else 0),
            "wrong assertion" if damage == "red_marker" else mutation.EXPECTED,
            "",
        )

    monkeypatch.setattr(mutation.subprocess, "run", execute)
    destination = tmp_path / "mutation"
    with pytest.raises(RuntimeError):
        mutation.run(destination)
    assert production.read_bytes() == original
    assert not (destination / "mutation.json").exists()
    assert (destination / "disconnected.log").exists()
    assert (destination / "restored.log").exists()


@pytest.mark.parametrize("outcome", ["error", "skip"])
def test_genuine_pytest_error_and_skip_are_rejected(tmp_path, outcome):
    import sys

    module = tmp_path / "test_invalid_evidence.py"
    module.write_text(
        "import pytest\n"
        + (
            "@pytest.fixture\ndef broken():\n    raise RuntimeError('actual setup error')\n"
            "def test_observation(broken):\n    assert False\n"
            if outcome == "error"
            else "def test_observation():\n    pytest.skip('actual skipped execution')\n"
        )
    )
    xml = tmp_path / "actual.xml"
    child = subprocess.run(
        [sys.executable, "-m", "pytest", "-c", "/dev/null", str(module), f"--junitxml={xml}", "-q"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert child.returncode == (1 if outcome == "error" else 0)
    with pytest.raises(ValueError, match="outcome mismatch"):
        load("verify_evidence").validate_junit(xml, 1)


def test_real_git_missing_historical_base_is_explicit(tmp_path, monkeypatch):
    probe = load("probe_base")
    checkout = tmp_path / "empty-repo"
    checkout.mkdir()
    subprocess.run(["git", "init", str(checkout)], check=True, capture_output=True)
    monkeypatch.setattr(probe, "ROOT", checkout)
    with pytest.raises(ValueError, match=probe.BASE) as raised:
        probe.run(tmp_path / "out")
    assert isinstance(raised.value.__cause__, subprocess.CalledProcessError)


def test_control_replays_current_parameterized_regression(tmp_path):
    destination = tmp_path / "real-pdf-control"
    load("replay_control").run(destination)
    receipt = json.loads((destination / "replay.json").read_text())
    assert receipt["reorder_after"] is True
    assert receipt["ids"] == ["1", "2"]
    assert receipt["changed"] == [True, False]
    assert receipt["classes"] == ["gate_provision_change"]
    assert len(list(destination.glob("*.pdf"))) == 2


@pytest.mark.parametrize("change", ["unchanged", "producer", "test", "missing", "corrupt"])
def test_immutable_archive_distinguishes_current_drift(tmp_path, monkeypatch, change):
    verifier = load("verify_evidence")
    checkout = tmp_path / "archive"
    checkout.mkdir()
    subprocess.run(["git", "init", str(checkout)], check=True, capture_output=True)
    inputs = {"producer.py": b"original producer\n", "test.py": b"original regression\n"}
    for name, content in inputs.items():
        (checkout / name).write_bytes(content)
    subprocess.run(["git", "-C", str(checkout), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(checkout),
            "-c",
            "user.name=control",
            "-c",
            "user.email=control@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "gc.auto=0",
            "commit",
            "-m",
            "immutable execution inputs",
        ],
        check=True,
        capture_output=True,
    )
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    bindings = {name: hashlib.sha256(content).hexdigest() for name, content in inputs.items()}
    monkeypatch.setattr(verifier, "ROOT", checkout)
    if change in ("producer", "test"):
        (checkout / f"{change}.py").write_bytes(b"future unrelated bytes\n")
    elif change == "missing":
        (checkout / "producer.py").unlink()
    elif change == "corrupt":
        bindings["producer.py"] = "0" * 64
        with pytest.raises(ValueError, match="immutable source/test binding mismatch"):
            verifier.verify_revision_inputs(bindings, revision)
        return
    drift = verifier.verify_revision_inputs(bindings, revision)
    assert drift == (
        {
            "producer": ["producer.py"],
            "test": ["test.py"],
            "missing": ["producer.py"],
            "unchanged": [],
        }[change]
    )
    if drift:
        with pytest.raises(ValueError, match="CURRENT_ADMISSION_FAIL"):
            verifier.require_current(drift)
    else:
        verifier.require_current(drift)


def test_current_admission_requires_fresh_integration_proof():
    with pytest.raises(ValueError, match="CURRENT_ADMISSION_FAIL"):
        load("verify_evidence").require_current(None)
