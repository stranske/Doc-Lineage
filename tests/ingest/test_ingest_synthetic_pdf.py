"""M1 ingest pipeline over a committed synthetic PDF.

The fixture ``tests/fixtures/synthetic_lpa.pdf`` is a hand-built, uncompressed,
two-page PDF containing synthetic LPA clause text. Nothing proprietary is
committed and no network or optional dependency is required, so these tests run
identically in every CI leg.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from doc_lineage.adapters import OFFLINE_BACKEND, segment_document
from doc_lineage.adapters.docling_segmenter import MAX_INGEST_BYTES
from doc_lineage.cli import main as cli_main
from doc_lineage.ingest import (
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_NAME,
    MANIFEST_SCHEMA_VERSION,
    SEGMENTS_FILENAME,
    ingest_document,
)
from doc_lineage.schema.validation import load_contract_schema

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_lpa.pdf"


def test_ingest_writes_valid_manifest(tmp_path: Path) -> None:
    """The named gate: ingest emits an artifact-manifest/v1 that validates."""
    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)

    manifest_path = tmp_path / MANIFEST_FILENAME
    segments_path = tmp_path / SEGMENTS_FILENAME
    assert manifest_path.is_file()
    assert segments_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    Draft202012Validator(load_contract_schema(MANIFEST_SCHEMA_NAME)).validate(manifest)

    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["tool"] == "doc-lineage-ingest"
    assert manifest["run_id"]

    # The manifest must describe the bytes actually written, not the bytes the
    # pipeline intended to write. This is what the deliberate-break gate removes.
    (artifact,) = manifest["artifacts"]
    assert artifact["path"] == SEGMENTS_FILENAME
    assert artifact["sha256"] == _sha256(segments_path)
    assert artifact["bytes"] == segments_path.stat().st_size

    assert manifest["source"]["sha256"] == result.source_sha256
    assert manifest["source"]["filename"] == FIXTURE.name


def test_segments_carry_page_pointers_and_stable_ids(tmp_path: Path) -> None:
    first = ingest_document(FIXTURE, output_dir=tmp_path / "a", allow_docling=False)
    second = ingest_document(FIXTURE, output_dir=tmp_path / "b", allow_docling=False)

    assert first.page_count == 2
    assert {segment.page for segment in first.segments} == {1, 2}
    assert [segment.segment_id for segment in first.segments] == [
        segment.segment_id for segment in second.segments
    ]

    text = " ".join(segment.text for segment in first.segments)
    assert "MANAGEMENT FEE" in text
    assert "Key Person Event" in text
    assert all(segment.char_count == len(segment.text) for segment in first.segments)
    assert all(segment.word_count > 0 for segment in first.segments)


def test_segments_payload_records_backend_and_text_layer(tmp_path: Path) -> None:
    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)
    payload = json.loads(result.segments_path.read_text(encoding="utf-8"))

    assert payload["backend"] == OFFLINE_BACKEND
    assert payload["source_sha256"] == result.source_sha256
    assert payload["pages_without_text_layer"] == []
    assert len(payload["segments"]) == len(result.segments)


def test_offline_backend_reports_missing_text_layer(tmp_path: Path) -> None:
    """A PDF with no readable content stream is a finding, not silence."""
    blank = tmp_path / "scanned.pdf"
    blank.write_bytes(b"%PDF-1.4\n%%EOF\n")

    segmented = segment_document(blank, allow_docling=False)

    assert segmented.pages_without_text_layer == (1,)
    with pytest.raises(ValueError, match="recognition fallback"):
        ingest_document(blank, output_dir=tmp_path / "out", allow_docling=False)


def test_ingest_rejects_a_missing_document(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_document(tmp_path / "absent.pdf", output_dir=tmp_path / "out")


def test_ingest_rejects_documents_above_size_limit(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.pdf"
    oversized.write_bytes(b"x" * (MAX_INGEST_BYTES + 1))

    with pytest.raises(ValueError, match="exceeds ingest size limit"):
        ingest_document(oversized, output_dir=tmp_path / "out", allow_docling=False)


def test_ingest_manifest_bytes_match_snapshot_length(tmp_path: Path) -> None:
    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)

    assert result.manifest["source"]["bytes"] == FIXTURE.stat().st_size


def test_ingest_rejects_empty_run_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run_id must be a non-empty string"):
        ingest_document(FIXTURE, output_dir=tmp_path, run_id="   ", allow_docling=False)


def test_offline_backend_rejects_binary_non_pdf(tmp_path: Path) -> None:
    binary = tmp_path / "deck.pptx"
    binary.write_bytes(b"PK\x03\x04fake-pptx-bytes")

    with pytest.raises(ValueError, match="non-PDF input requires Docling"):
        segment_document(binary, allow_docling=False)


def test_cli_ingest_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli_main(
        [
            "ingest",
            str(FIXTURE),
            "--output",
            str(tmp_path / "run"),
            "--run-id",
            "fixed-run",
            "--no-docling",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "run_id=fixed-run" in captured.out
    assert (tmp_path / "run" / MANIFEST_FILENAME).is_file()


def test_cli_ingest_reports_a_missing_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli_main(["ingest", str(tmp_path / "absent.pdf"), "--output", str(tmp_path)])

    assert exit_code == 1
    assert "does not exist" in capsys.readouterr().err


def test_console_script_runs_the_documented_command(tmp_path: Path) -> None:
    """`doc-lineage ingest <fixture> --output <dir>` exits 0, as the issue requires."""
    project_root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(project_root), "-q"],
        check=True,
        capture_output=True,
        text=True,
    )
    script = shutil.which("doc-lineage")
    assert script is not None, "doc-lineage console script must be installed"
    command = [
        script,
        "ingest",
        str(FIXTURE),
        "--output",
        str(tmp_path / "run"),
        "--no-docling",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "run" / MANIFEST_FILENAME).is_file()


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cli_warns_about_pages_without_a_text_layer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mixed document ingests and still surfaces the pages needing recognition."""
    mixed = tmp_path / "mixed.pdf"
    mixed.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Length 26 >>\nstream\nBT (Readable clause) Tj ET\nendstream\nendobj\n"
        b"2 0 obj\n<< /Type /Page /Contents 1 0 R >>\nendobj\n"
        b"3 0 obj\n<< /Length 5 /Filter /DCTDecode >>\nstream\nimage\nendstream\nendobj\n"
        b"4 0 obj\n<< /Type /Page /Contents 3 0 R >>\nendobj\n%%EOF\n"
    )

    exit_code = cli_main(["ingest", str(mixed), "--output", str(tmp_path / "run"), "--no-docling"])

    assert exit_code == 0
    assert "no text layer on page(s) 2" in capsys.readouterr().out
