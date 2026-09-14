"""Tests for document identity and manifest generation."""

from __future__ import annotations

import json
import os
import shutil
import sys
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


@pytest.mark.parametrize("empty_library", [False, True])
def test_unchanged_manifest_is_not_rewritten(tmp_path: Path, empty_library: bool) -> None:
    library = tmp_path / "library"
    if empty_library:
        library.mkdir()
    else:
        shutil.copytree(FIXTURE_ROOT, library)
    output = tmp_path / "manifest.jsonl"
    write_manifest(library, output)
    original = output.read_bytes()
    # Use a fixed old timestamp so the check does not depend on clock resolution.
    os.utime(output, ns=(1_000_000_000, 1_000_000_000))
    previous_mtime = output.stat().st_mtime_ns

    write_manifest(library, output)

    assert output.read_bytes() == original
    assert output.stat().st_mtime_ns == previous_mtime

    added = library / "new_manager/reports/new.pdf"
    added.parent.mkdir(parents=True)
    added.write_bytes(b"new document")
    write_manifest(library, output)
    assert output.read_bytes() != original
    assert "new_manager/reports/new.pdf" in read_manifest(output)


def test_build_manifest_script_entry_point(tmp_path: Path) -> None:
    library = tmp_path / "library"
    shutil.copytree(FIXTURE_ROOT, library)
    output = tmp_path / "manifest.jsonl"
    import subprocess

    result = subprocess.run(
        [
            sys.executable,
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


@pytest.mark.parametrize("root_is_file", [False, True])
def test_invalid_library_root_preserves_existing_manifest(
    tmp_path: Path, root_is_file: bool
) -> None:
    library = tmp_path / "library"
    shutil.copytree(FIXTURE_ROOT, library)
    output = tmp_path / "manifest.jsonl"
    write_manifest(library, output)
    original = output.read_bytes()
    library.rename(tmp_path / "moved_library")
    if root_is_file:
        library.write_bytes(b"not a directory")

    with pytest.raises(ValueError, match="root must be an existing directory"):
        write_manifest(library, output)

    assert output.read_bytes() == original
    with pytest.raises(ValueError, match="root must be an existing directory"):
        build_manifest_rows(library)


def test_supersession_is_path_scoped_with_duplicate_content(tmp_path: Path) -> None:
    library = tmp_path / "library"
    docs = {
        "alpha/reports/001_report.pdf": b"old",
        "alpha/reports/002_report.pdf": b"new",
        "beta/reports/copy.pdf": b"new",
        "gamma/reports/001_report.pdf": b"same",
        "gamma/reports/002_report.pdf": b"same",
    }
    for relative, content in docs.items():
        path = library / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    rows = _rows_by_path(library)
    assert rows["alpha/reports/002_report.pdf"]["supersedes"] == sha256_bytes(b"old")
    assert (
        rows["alpha/reports/002_report.pdf"]["supersession_evidence"] == "numeric_prefix_separator"
    )
    for relative in docs.keys() - {"alpha/reports/002_report.pdf"}:
        assert rows[relative]["supersedes"] is None
        assert rows[relative]["supersession_evidence"] is None


@pytest.mark.parametrize("existing", [False, True])
def test_document_output_inside_library_is_rejected(tmp_path: Path, existing: bool) -> None:
    library = tmp_path / "library"
    library.mkdir()
    output = library / "manifest.txt"
    if existing:
        output.write_bytes(b"original document")
    with pytest.raises(ValueError, match="output.*document"):
        write_manifest(library, output)
    if existing:
        assert output.read_bytes() == b"original document"
    else:
        assert not output.exists()


@pytest.mark.parametrize("annotation", ["present", "absent"])
def test_text_layer_annotation_survives_unchanged_content(tmp_path: Path, annotation: str) -> None:
    library = tmp_path / "library"
    doc = library / "alpha/reports/report.pdf"
    doc.parent.mkdir(parents=True)
    doc.write_bytes(b"original")
    output = library / "manifest.jsonl"
    write_manifest(library, output)
    payload = json.loads(output.read_text())
    payload["text_layer"] = annotation
    annotated = json.dumps(payload) + "\n"
    output.write_text(annotated)
    write_manifest(library, output)
    assert output.read_text() == annotated
    doc.write_bytes(b"changed")
    write_manifest(library, output)
    assert json.loads(output.read_text())["text_layer"] == "unknown"


def test_invalid_prior_text_layer_is_reset(tmp_path: Path) -> None:
    library = tmp_path / "library"
    doc = library / "alpha/reports/report.pdf"
    doc.parent.mkdir(parents=True)
    doc.write_bytes(b"original")
    output = tmp_path / "manifest.jsonl"
    write_manifest(library, output)
    payload = json.loads(output.read_text())
    payload["text_layer"] = "not-a-state"
    output.write_text(json.dumps(payload) + "\n")
    write_manifest(library, output)
    assert json.loads(output.read_text())["text_layer"] == "unknown"


@pytest.mark.parametrize("separator", ["_", "-", "."])
def test_numeric_resupply_links_unnumbered_original_and_orders_numerically(
    tmp_path: Path, separator: str
) -> None:
    directory = tmp_path / "alpha/reports/2024"
    directory.mkdir(parents=True)
    versions = ["report.pdf", f"2{separator}report.pdf", f"10{separator}report.pdf"]
    for filename in reversed(versions):
        (directory / filename).write_bytes(filename.encode())

    output = tmp_path / "manifest.jsonl"
    write_manifest(tmp_path, output)
    rows = {Path(path).name: json.loads(line) for path, line in read_manifest(output).items()}
    assert rows[versions[0]]["supersedes"] is None
    assert rows[versions[0]]["supersession_evidence"] is None
    for older, newer in zip(versions, versions[1:], strict=False):
        assert rows[newer]["supersedes"] == rows[older]["stable_id"]
        assert rows[newer]["supersession_evidence"] == "numeric_prefix_separator"


@pytest.mark.parametrize("duplicate_content", [False, True])
def test_equal_numeric_prefixes_do_not_invent_version_order(
    tmp_path: Path, duplicate_content: bool
) -> None:
    directory = tmp_path / "alpha/reports"
    directory.mkdir(parents=True)
    documents = {
        "report.pdf": b"original",
        "1_report.pdf": b"first",
        "01-report.pdf": b"first" if duplicate_content else b"conflicting",
        "2_report.pdf": b"second",
    }
    for filename, content in documents.items():
        (directory / filename).write_bytes(content)
    rows = {Path(row.path).name: row for row in build_manifest_rows(tmp_path)}
    assert rows["report.pdf"].supersedes is None
    for filename in ("1_report.pdf", "01-report.pdf", "2_report.pdf"):
        row = rows[filename]
        if duplicate_content:
            expected = b"first" if filename == "2_report.pdf" else b"original"
            assert row.supersedes == sha256_bytes(expected)
            assert row.supersession_evidence == "numeric_prefix_separator"
        else:
            assert row.supersedes is None
            assert row.supersession_evidence is None
