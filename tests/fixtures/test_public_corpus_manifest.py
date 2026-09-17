"""Tests for the fleet-wide public fixture corpus manifest."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "public_corpus" / "manifest.json"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_at_least_one_entry() -> None:
    manifest = _load_manifest()
    assert manifest["schema_version"] == "artifact-manifest/v1"
    assert len(manifest["artifacts"]) >= 1


def test_manifest_sha256_fields_are_valid() -> None:
    manifest = _load_manifest()
    for artifact in manifest["artifacts"]:
        assert SHA256_RE.fullmatch(artifact["sha256"])
        content_sha256 = artifact.get("content_sha256")
        if content_sha256 is not None:
            assert SHA256_RE.fullmatch(content_sha256)
            assert content_sha256 == artifact["sha256"]


def test_manifest_has_calpers_entry() -> None:
    manifest = _load_manifest()
    calpers_entries = [
        artifact
        for artifact in manifest["artifacts"]
        if artifact.get("artifact_id") == "calpers-ic-default"
    ]
    assert calpers_entries, "expected calpers-ic-default corpus entry"
    entry = calpers_entries[0]
    assert entry["doc_type_id"] == "calpers_investment_committee"
    assert (
        entry["source_url"]
        == "https://www.calpers.ca.gov/about/board/board-meetings/invest-202603-0"
    )
    assert SHA256_RE.fullmatch(entry["content_sha256"])
    assert entry["content_sha256"] == entry["sha256"]


def test_present_public_file_wrong_digest_fails_validation(tmp_path: Path) -> None:
    from scripts.validate_fixture_manifest import validate_manifest

    manifest = _load_manifest()
    calpers_path = REPO_ROOT / "tests/fixtures/public_corpus/calpers/ic/default.pdf"
    assert calpers_path.is_file(), "CalPERS fixture PDF must be present for digest checks"
    corrupted = json.loads(json.dumps(manifest))
    for artifact in corrupted["artifacts"]:
        if artifact.get("artifact_id") == "calpers-ic-default":
            artifact["sha256"] = "0" * 64
            artifact["content_sha256"] = "0" * 64
    errors = validate_manifest(corrupted)
    assert any("calpers/ic/default.pdf" in message for message in errors)


def test_validate_fixture_manifest_script_passes() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_fixture_manifest.py"),
            "--manifest",
            str(MANIFEST_PATH),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_corrupt_sha256_fails_validation() -> None:
    from scripts.validate_fixture_manifest import validate_manifest

    manifest = _load_manifest()
    corrupted = json.loads(json.dumps(manifest))
    corrupted["artifacts"][0]["sha256"] = "0" * 63 + "x"
    errors = validate_manifest(corrupted)
    assert errors, "corrupt sha256 must fail validation (deliberate-break gate)"
