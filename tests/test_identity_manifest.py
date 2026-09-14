"""Tests for document identity and manifest generation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from doc_lineage.identity import compute_identity, sha256_bytes
from doc_lineage.manifest import build_manifest_rows, read_manifest, write_manifest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "library"


def _rows_by_path(root: Path) -> dict[str, dict[str, object]]:
    return {row.path: json.loads(row.to_json()) for row in build_manifest_rows(root)}


def test_rename_preserves_stable_id_and_sha256(tmp_path: Path) -> None:
    library = tmp_path / "library"
    doc_dir = library / "manager_alpha" / "lpa" / "2024"
    doc_dir.mkdir(parents=True)
    original = doc_dir / "001_terms.pdf"
    original.write_bytes(b"rename-me")
    before = compute_identity(library, original)

    renamed = doc_dir / "001_terms_renamed.pdf"
    original.rename(renamed)
    after = compute_identity(library, renamed)

    assert after.filename != before.filename
    assert after.stable_id == before.stable_id
    assert after.sha256 == before.sha256


def test_duplicate_content_paths_share_stable_id() -> None:
    rows = _rows_by_path(FIXTURE_ROOT)
    primary = rows["manager_beta/side_letters/2023/beta_side.pdf"]
    duplicate = rows["manager_beta/side_letters/2023/archive/beta_side_copy.pdf"]
    assert primary["stable_id"] == duplicate["stable_id"]
    assert primary["sha256"] == duplicate["sha256"]
    assert primary["path"] != duplicate["path"]


def test_numeric_resupply_records_supersedes_and_evidence() -> None:
    rows = _rows_by_path(FIXTURE_ROOT)
    older = rows["manager_alpha/lpa/2024/001_alpha_terms.pdf"]
    newer = rows["manager_alpha/lpa/2024/002_alpha_terms.pdf"]
    assert newer["supersedes"] == older["stable_id"]
    assert newer["supersession_evidence"] == "numeric_prefix_separator"


def test_text_layer_defaults_to_unknown() -> None:
    rows = _rows_by_path(FIXTURE_ROOT)
    assert all(row["text_layer"] == "unknown" for row in rows.values())


def test_second_run_is_byte_identical(tmp_path: Path) -> None:
    library = tmp_path / "library"
    shutil.copytree(FIXTURE_ROOT, library)
    output = tmp_path / "manifest.jsonl"
    write_manifest(library, output)
    first = output.read_bytes()
    write_manifest(library, output)
    second = output.read_bytes()
    assert first == second


def test_build_manifest_script_entry_point(tmp_path: Path) -> None:
    library = tmp_path / "library"
    shutil.copytree(FIXTURE_ROOT, library)
    output = tmp_path / "manifest.jsonl"
    import subprocess

    result = subprocess.run(
        [
            "python3",
            "scripts/build_manifest.py",
            str(library),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 5
    payload = json.loads(lines[0])
    assert payload["text_layer"] == "unknown"


def test_deliberate_break_path_based_stable_id_fails_rename_test(tmp_path: Path) -> None:
    """Deliberate-break gate: path-derived stable_id must fail the rename invariant."""

    def path_based_stable_id(content: bytes, path: Path) -> str:
        return sha256_bytes(str(path).encode("utf-8"))

    library = tmp_path / "library"
    doc_dir = library / "manager_alpha" / "lpa" / "2024"
    doc_dir.mkdir(parents=True)
    original = doc_dir / "001_terms.pdf"
    original.write_bytes(b"rename-me")
    before = path_based_stable_id(original.read_bytes(), original)
    renamed = doc_dir / "001_terms_renamed.pdf"
    original.rename(renamed)
    after = path_based_stable_id(renamed.read_bytes(), renamed)
    with pytest.raises(AssertionError):
        assert after == before


def test_content_based_stable_id_passes_rename_test(tmp_path: Path) -> None:
    library = tmp_path / "library"
    doc_dir = library / "manager_alpha" / "lpa" / "2024"
    doc_dir.mkdir(parents=True)
    original = doc_dir / "001_terms.pdf"
    original.write_bytes(b"rename-me")
    before = compute_identity(library, original)
    renamed = doc_dir / "001_terms_renamed.pdf"
    original.rename(renamed)
    after = compute_identity(library, renamed)
    assert after.stable_id == before.stable_id


def test_incremental_manifest_preserves_unchanged_lines(tmp_path: Path) -> None:
    library = tmp_path / "library"
    shutil.copytree(FIXTURE_ROOT, library)
    output = tmp_path / "manifest.jsonl"
    write_manifest(library, output)
    preserved = read_manifest(output)
    write_manifest(library, output)
    assert read_manifest(output) == preserved
