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
from io import BytesIO
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
    # Evidence objects are listed alongside the segments artifact (see
    # tests/emit/test_evidence_object.py), so select the one under test.
    (artifact,) = [entry for entry in manifest["artifacts"] if entry["path"] == SEGMENTS_FILENAME]
    assert artifact["path"] == SEGMENTS_FILENAME
    assert artifact["sha256"] == _sha256(segments_path)
    assert artifact["bytes"] == segments_path.stat().st_size

    assert manifest["source"]["sha256"] == result.source_sha256
    assert manifest["source"]["filename"] == FIXTURE.name


def test_offline_ingest_preserves_euro_amount_in_segments_and_evidence(tmp_path: Path) -> None:
    from reportlab.pdfgen import canvas

    source = tmp_path / "euro.pdf"
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "The fee is €50.")
    pdf.save()
    source.write_bytes(buffer.getvalue())

    result = ingest_document(source, output_dir=tmp_path / "out", allow_docling=False)

    assert [segment.text for segment in result.segments] == ["The fee is €50."]
    written = json.loads(result.segments_path.read_text(encoding="utf-8"))
    assert [segment["text"] for segment in written["segments"]] == ["The fee is €50."]
    assert len(result.evidence) == 1
    assert result.evidence[0]["excerpt"] == "The fee is €50."
    assert result.evidence[0]["locator"]["page"] == 0
    assert result.evidence[0]["method"] == "text"
    assert result.evidence_dir is not None
    (evidence_path,) = result.evidence_dir.glob("*.json")
    assert json.loads(evidence_path.read_text(encoding="utf-8")) == result.evidence[0]
    assert result.coverage_status == "complete"


def test_segments_carry_page_pointers_and_stable_ids(tmp_path: Path) -> None:
    first = ingest_document(FIXTURE, output_dir=tmp_path / "a", allow_docling=False)
    second = ingest_document(FIXTURE, output_dir=tmp_path / "b", allow_docling=False)

    assert first.page_count == 2
    assert {segment.page for segment in first.segments} == {1, 2}
    assert {evidence["locator"]["page"] for evidence in first.evidence} == {0, 1}
    for segment in first.segments:
        assert f"-p{segment.page:04d}-" in segment.segment_id
    assert [segment.segment_id for segment in first.segments] == [
        segment.segment_id for segment in second.segments
    ]

    text = " ".join(segment.text for segment in first.segments)
    assert "MANAGEMENT FEE" in text
    assert "Key Person Event" in text
    assert all(segment.char_count == len(segment.text) for segment in first.segments)
    assert all(segment.word_count > 0 for segment in first.segments)


def test_evidence_locators_identify_the_physical_pdf_page(tmp_path: Path) -> None:
    from pypdf import PdfReader

    reader = PdfReader(FIXTURE)
    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)
    assert len(reader.pages) == result.page_count == 2
    segments = {segment.segment_id: segment for segment in result.segments}
    for path in (tmp_path / "evidence").glob("*.json"):
        evidence = json.loads(path.read_text(encoding="utf-8"))
        page = evidence["locator"]["page"]
        assert 0 <= page < len(reader.pages)
        segment = segments[evidence["fact_ref"].removeprefix("segment:")]
        assert page == segment.page - 1
        assert evidence["excerpt"] == segment.text
        page_text = " ".join(reader.pages[page].extract_text().split())
        assert evidence["excerpt"] in page_text
    assert len(list((tmp_path / "evidence").glob("*.json"))) == len(result.segments)


def test_reused_output_removes_previous_document_evidence(tmp_path: Path) -> None:
    """A completed run must not expose the previous document's evidence."""
    output = tmp_path / "run"
    first = ingest_document(FIXTURE, output_dir=output, allow_docling=False)
    previous_paths = set((output / "evidence").glob("*.json"))
    assert previous_paths

    other = tmp_path / "other.pdf"
    other.write_bytes(FIXTURE.read_bytes().replace(b"MANAGEMENT FEE", b"DIFFERENT FEE!"))
    second = ingest_document(other, output_dir=output, allow_docling=False)

    assert second.source_sha256 != first.source_sha256
    expected_paths = {
        output / artifact["path"]
        for artifact in second.manifest["artifacts"]
        if artifact["kind"] == "evidence"
    }
    assert expected_paths
    assert set((output / "evidence").iterdir()) == expected_paths
    assert not any(path.exists() for path in previous_paths)
    for path in expected_paths:
        assert first.source_sha256 not in path.read_text(encoding="utf-8")

    # Repeating the current document must retain all of its evidence.
    ingest_document(other, output_dir=output, allow_docling=False)
    assert set((output / "evidence").iterdir()) == expected_paths


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


def test_ingest_manifest_bytes_match_snapshot_length(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from doc_lineage import ingest as ingest_module

    source = tmp_path / "snapshot.pdf"
    shutil.copy(FIXTURE, source)
    original = ingest_module.read_bounded_bytes
    snapshot_len = source.stat().st_size

    def _snapshot_then_mutate(path: Path, max_bytes: int) -> bytes:
        payload = original(path, max_bytes)
        path.write_bytes(b"mutated-after-snapshot")
        return payload

    monkeypatch.setattr(ingest_module, "read_bounded_bytes", _snapshot_then_mutate)

    result = ingest_document(source, output_dir=tmp_path / "out", allow_docling=False)

    assert result.manifest["source"]["bytes"] == snapshot_len
    assert source.stat().st_size != snapshot_len


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


def _write_ocr_ingest_pdf(path: Path, *, native: bool = False, scanned_pages: int = 1) -> None:
    from PIL import Image, ImageDraw
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = Image.new("RGB", (240, 120), "white")
    ImageDraw.Draw(image).text((20, 50), "SYNTHETIC SCANNED CLAUSE", fill="black")
    pdf = canvas.Canvas(str(path), pageCompression=0)
    if native:
        pdf.drawString(72, 720, "Native management fee clause")
        pdf.showPage()
    for _ in range(scanned_pages):
        pdf.drawImage(ImageReader(image), 72, 600, width=240, height=120)
        pdf.showPage()
    pdf.save()


def test_ingest_recovers_image_only_page(tmp_path: Path) -> None:
    from doc_lineage.extract.ocr import CallableOCRBackend

    source = tmp_path / "scanned.pdf"
    _write_ocr_ingest_pdf(source)
    digest = _sha256(source)
    seen = []

    def recognize(image, *, rotation=0):
        seen.append(image.size)
        assert image.convert("L").getextrema()[0] < 255
        return "Recovered scanned clause\n\nSecond paragraph"

    result = ingest_document(
        source,
        output_dir=tmp_path / "out",
        allow_docling=False,
        ocr_backend=CallableOCRBackend(recognize),
    )
    payload = json.loads(result.segments_path.read_text())
    assert seen and min(seen[0]) > 1
    assert payload["source_sha256"] == digest == result.manifest["source"]["sha256"]
    assert payload["pages_without_text_layer"] == [1]
    assert payload["unreadable_pages"] == []
    assert payload["coverage"] == {
        "status": "complete",
        "pages_total": 1,
        "pages_with_text_layer": 0,
        "pages_recognized": 1,
        "pages_unreadable": 0,
    }
    assert [s["text"] for s in payload["segments"]] == [
        "Recovered scanned clause",
        "Second paragraph",
    ]
    assert all(s["method"] == "ocr" and s["page"] == 1 for s in payload["segments"])
    assert all(e["method"] == "ocr" and e["locator"]["page"] == 0 for e in result.evidence)
    assert result.evidence[0]["excerpt"] == "Recovered scanned clause"
    for artifact in result.manifest["artifacts"]:
        actual = result.output_dir / artifact["path"]
        assert _sha256(actual) == artifact["sha256"]
        assert actual.stat().st_size == artifact["bytes"]
    repeated = ingest_document(
        source,
        output_dir=tmp_path / "repeat",
        allow_docling=False,
        ocr_backend=CallableOCRBackend(recognize),
    )
    assert [s.segment_id for s in repeated.segments] == [s.segment_id for s in result.segments]
    assert repeated.evidence == result.evidence


def test_mixed_ingest_keeps_page_methods_and_partial_coverage(tmp_path: Path) -> None:
    from doc_lineage.extract.ocr import CallableOCRBackend

    source = tmp_path / "mixed.pdf"
    _write_ocr_ingest_pdf(source, native=True, scanned_pages=2)
    calls = []

    def recognize(image, *, rotation=0):
        calls.append(image.size)
        return "Recovered page two" if len(calls) == 1 else None

    result = ingest_document(
        source,
        output_dir=tmp_path / "out",
        allow_docling=False,
        ocr_backend=CallableOCRBackend(recognize),
    )
    payload = json.loads(result.segments_path.read_text())
    assert len(calls) == 2  # never OCR the native page
    assert [(s.page, s.method) for s in result.segments] == [(1, "text"), (2, "ocr")]
    assert [(e["locator"]["page"], e["method"]) for e in result.evidence] == [
        (0, "text"),
        (1, "ocr"),
    ]
    assert payload["pages_without_text_layer"] == [2, 3]
    assert payload["unreadable_pages"] == [3]
    assert payload["coverage"] == {
        "status": "partial",
        "pages_total": 3,
        "pages_with_text_layer": 1,
        "pages_recognized": 1,
        "pages_unreadable": 1,
    }
    assert result.unreadable_pages == (3,)
    assert result.coverage_status == "partial"


@pytest.mark.parametrize("failure", ["absent", "empty", "exception", "disabled", "renderer"])
def test_unavailable_ingest_ocr_never_fabricates_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    from doc_lineage import ingest as ingest_module
    from doc_lineage.extract import pdf as pdf_module
    from doc_lineage.extract.ocr import CallableOCRBackend

    source = tmp_path / "mixed.pdf"
    _write_ocr_ingest_pdf(source, native=True)
    calls = []

    def recognize(image, *, rotation=0):
        calls.append(image.size)
        if failure == "exception":
            raise RuntimeError("recognition unavailable")
        return "   "

    monkeypatch.setattr(ingest_module, "default_ocr_backend", lambda: None)
    if failure == "renderer":
        monkeypatch.setattr(pdf_module, "_render_page_image", lambda page: None)
    result = ingest_document(
        source,
        output_dir=tmp_path / "out",
        allow_docling=False,
        ocr_backend=None if failure == "absent" else CallableOCRBackend(recognize),
        ocr_enabled=failure != "disabled",
    )
    payload = json.loads(result.segments_path.read_text())
    assert result.unreadable_pages == (2,)
    assert result.coverage_status == "partial"
    assert payload["unreadable_pages"] == [2]
    assert payload["coverage"]["pages_recognized"] == 0
    assert len(result.segments) == 1 and result.segments[0].method == "text"
    assert bool(calls) == (failure in {"empty", "exception"})

    scanned = tmp_path / "all-scanned.pdf"
    _write_ocr_ingest_pdf(scanned)
    failed_output = tmp_path / "failed"
    with pytest.raises(ValueError, match="no text segments recovered"):
        ingest_document(
            scanned,
            output_dir=failed_output,
            allow_docling=False,
            ocr_backend=None if failure == "absent" else CallableOCRBackend(recognize),
            ocr_enabled=failure != "disabled",
        )
    assert not failed_output.exists()


def test_ocr_ingest_uses_immutable_source_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from doc_lineage import ingest as ingest_module
    from doc_lineage.extract.ocr import CallableOCRBackend

    source = tmp_path / "scanned.pdf"
    _write_ocr_ingest_pdf(source)
    expected_sha, expected_size = _sha256(source), source.stat().st_size
    read = ingest_module.read_bounded_bytes

    def snapshot_then_mutate(path, limit):
        data = read(path, limit)
        path.write_bytes(b"changed after snapshot")
        return data

    monkeypatch.setattr(ingest_module, "read_bounded_bytes", snapshot_then_mutate)
    result = ingest_document(
        source,
        output_dir=tmp_path / "out",
        allow_docling=False,
        ocr_backend=CallableOCRBackend(lambda image, rotation=0: "snapshot OCR clause"),
    )
    assert result.source_sha256 == expected_sha
    assert result.manifest["source"]["bytes"] == expected_size
    assert result.evidence[0]["excerpt"] == "snapshot OCR clause"
    assert _sha256(source) != expected_sha


def test_cli_ocr_coverage_and_unrecoverable_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from doc_lineage import ingest as ingest_module
    from doc_lineage.extract.ocr import CallableOCRBackend

    source = tmp_path / "scanned.pdf"
    _write_ocr_ingest_pdf(source)
    monkeypatch.setattr(
        ingest_module,
        "default_ocr_backend",
        lambda: CallableOCRBackend(
            lambda image, rotation=0: "local OCR clause",
        ),
    )
    command = ["ingest", str(source), "--no-docling", "--output", str(tmp_path / "out")]
    assert cli_main(command) == 0
    assert "coverage=complete" in capsys.readouterr().out
    failed_output = tmp_path / "failed"
    assert (
        cli_main(
            ["ingest", str(source), "--no-docling", "--no-ocr", "--output", str(failed_output)]
        )
        == 1
    )
    assert "no text segments recovered" in capsys.readouterr().err
    assert not failed_output.exists()
    mixed = tmp_path / "mixed.pdf"
    _write_ocr_ingest_pdf(mixed, native=True)
    assert (
        cli_main(
            [
                "ingest",
                str(mixed),
                "--no-docling",
                "--no-ocr",
                "--output",
                str(tmp_path / "partial"),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "coverage=partial" in out and "no text layer on page(s) 2" in out
