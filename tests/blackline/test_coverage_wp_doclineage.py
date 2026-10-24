"""Tests covering integrity gates and rejection paths in blackline.py (WP doclineage)."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reportlab.pdfgen.canvas import Canvas

from doc_lineage.blackline import (
    DEFAULT_HEADER_CONFIDENCE_THRESHOLD,
    _canonical_bytes,
    _json_object,
    _run_file,
    _validate_docx,
    create_section_comparison,
    load_comparison_record,
    load_section_comparison,
    load_section_ingest,
)
from doc_lineage.identity import sha256_bytes
from doc_lineage.ingest import ingest_document


def _create_sample_pdf(path: Path, fee_text: str = "The fee is two percent.") -> None:
    canvas = Canvas(str(path), invariant=True)
    canvas.drawString(72, 720, "1. MANAGEMENT FEE")
    canvas.drawString(72, 700, fee_text)
    canvas.showPage()
    canvas.drawString(72, 720, "2. TERM")
    canvas.drawString(72, 700, "The term is ten years.")
    canvas.showPage()
    canvas.save()


def _build_valid_ingest(output_dir: Path, pdf_path: Path) -> Path:
    ingest_document(pdf_path, output_dir=output_dir, allow_docling=False, ocr_enabled=False)
    return output_dir


def _update_manifest(run_dir: Path, modifier: Callable[[dict[str, Any]], None]) -> None:
    manifest_path = run_dir / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    modifier(manifest)
    manifest_path.write_bytes(json.dumps(manifest, indent=2).encode())


def _update_segments(run_dir: Path, modifier: Callable[[dict[str, Any]], None]) -> None:
    segments_path = run_dir / "segments.json"
    payload = json.loads(segments_path.read_bytes())
    modifier(payload)
    new_bytes = json.dumps(payload, indent=2).encode()
    segments_path.write_bytes(new_bytes)

    def sync_manifest(m: dict[str, Any]) -> None:
        for art in m.get("artifacts", []):
            if art.get("path") == "segments.json":
                art["sha256"] = sha256_bytes(new_bytes)
                art["bytes"] = len(new_bytes)

    _update_manifest(run_dir, sync_manifest)


def _update_comparison_record(target: Path, modifier: Callable[[dict[str, Any]], None]) -> None:
    record = json.loads(target.read_bytes())
    record.pop("record_sha256", None)
    modifier(record)
    record["record_sha256"] = sha256_bytes(_canonical_bytes(record))
    target.write_bytes(_canonical_bytes(record))


def _create_valid_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("word/document.xml", b"<document>content</document>")
    return buf.getvalue()


@pytest.fixture
def valid_ingest(tmp_path: Path) -> Path:
    pdf = tmp_path / "sample.pdf"
    _create_sample_pdf(pdf)
    out = tmp_path / "valid_ingest"
    _build_valid_ingest(out, pdf)
    return out


@pytest.fixture
def paired_runs(tmp_path: Path) -> tuple[Path, Path]:
    left_pdf = tmp_path / "left.pdf"
    right_pdf = tmp_path / "right.pdf"
    _create_sample_pdf(left_pdf, fee_text="The fee is two percent.")
    _create_sample_pdf(right_pdf, fee_text="The fee is three percent.")
    left_run = tmp_path / "left_run"
    right_run = tmp_path / "right_run"
    _build_valid_ingest(left_run, left_pdf)
    _build_valid_ingest(right_run, right_pdf)
    return left_run, right_run


# --- Group 1: _json_object & _run_file ---


def test_json_object_rejects_non_dict() -> None:
    with pytest.raises(ValueError, match=r"^invalid manifest$"):
        _json_object(b'["not", "a", "dict"]', "manifest")


def test_json_object_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match=r"^invalid payload$"):
        _json_object(b"{malformed json", "payload")


def test_run_file_rejects_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^unsafe ingest artifact path$"):
        _run_file(tmp_path, "../outside.json")


def test_run_file_rejects_missing_artifact(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError, match=r"^missing or unreadable ingest artifact: nonexistent\.json$"
    ):
        _run_file(tmp_path, "nonexistent.json")


# --- Group 2: load_section_ingest ---


def test_load_section_ingest_rejects_invalid_manifest_contract(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["schema_version"] = "invalid-schema-contract"

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^invalid ingest manifest$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_non_doclineage_tool(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["tool"] = "external-tool"

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^not a doc-lineage ingest manifest$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_missing_source_binding(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        del m["source"]

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^missing original source binding$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_invalid_source_digest(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["source"]["sha256"] = "invalid_not_64_hex_digits"

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^invalid original source digest$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_duplicate_artifact_binding(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["artifacts"].append(dict(m["artifacts"][0]))

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^duplicate ingest artifact binding$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_artifact_hash_size_mismatch(valid_ingest: Path) -> None:
    seg_file = valid_ingest / "segments.json"
    seg_file.write_bytes(seg_file.read_bytes() + b" ")
    with pytest.raises(ValueError, match=r"^ingest artifact hash/size mismatch: segments\.json$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_missing_retained_original(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["artifacts"] = [a for a in m["artifacts"] if not a["path"].startswith("source-")]

    _update_manifest(valid_ingest, mod)
    with pytest.raises(
        ValueError,
        match=r"^missing retained original source; re-ingest into a new run directory$",
    ):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_original_source_binding_mismatch(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["source"]["bytes"] = m["source"]["bytes"] + 1

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^original source binding mismatch$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_non_pdf_original(valid_ingest: Path) -> None:
    orig_file = next(valid_ingest.glob("source-*.bin"))
    non_pdf_data = b"NOT_A_PDF_STREAM_CONTENT_HERE"
    orig_file.write_bytes(non_pdf_data)

    def mod(m: dict[str, Any]) -> None:
        digest = sha256_bytes(non_pdf_data)
        m["source"]["sha256"] = digest
        m["source"]["bytes"] = len(non_pdf_data)
        renamed = valid_ingest / f"source-{digest}.bin"
        orig_file.rename(renamed)
        for art in m["artifacts"]:
            if art["path"].startswith("source-"):
                art["path"] = renamed.name
                art["sha256"] = digest
                art["bytes"] = len(non_pdf_data)

    _update_manifest(valid_ingest, mod)
    with pytest.raises(
        ValueError,
        match=r"^section pairing requires PDF ingests; native DOCX is a separate mode$",
    ):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_missing_segments_binding(valid_ingest: Path) -> None:
    def mod(m: dict[str, Any]) -> None:
        m["artifacts"] = [a for a in m["artifacts"] if a["path"] != "segments.json"]

    _update_manifest(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^missing segments artifact binding$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_segments_source_or_schema_mismatch(valid_ingest: Path) -> None:
    def mod(p: dict[str, Any]) -> None:
        p["source_sha256"] = "0" * 64

    _update_segments(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^segments source/schema binding mismatch$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_empty_segments_payload(valid_ingest: Path) -> None:
    def mod(p: dict[str, Any]) -> None:
        p["segments"] = []

    _update_segments(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^invalid empty segments payload$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_invalid_segment_record(valid_ingest: Path) -> None:
    def mod(p: dict[str, Any]) -> None:
        p["segments"][0]["unexpected_field"] = "unexpected_value"

    _update_segments(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^invalid segment record$"):
        load_section_ingest(valid_ingest)


def test_load_section_ingest_rejects_invalid_segment_content_order_binding(
    valid_ingest: Path,
) -> None:
    def mod(p: dict[str, Any]) -> None:
        p["segments"][0]["order"] = 99

    _update_segments(valid_ingest, mod)
    with pytest.raises(ValueError, match=r"^invalid segment content/order binding$"):
        load_section_ingest(valid_ingest)


# --- Group 3: _section_comparison ---


def test_section_comparison_rejects_invalid_threshold(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    with pytest.raises(ValueError, match=r"^threshold must be finite and between 0 and 1$"):
        create_section_comparison(left, right, store=store, threshold=1.5)


# --- Group 4: load_section_comparison ---


def test_load_section_comparison_rejects_invalid_id_format(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    with pytest.raises(
        ValueError, match=r"^not a comparison ID; expected cmp_<32 lowercase hex>, never a path$"
    ):
        load_section_comparison("invalid-comparison-id", store=store)


def test_load_section_comparison_rejects_symlink(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"
    backup = store / f"{cid}.bak"
    target.rename(backup)
    target.symlink_to(backup)
    with pytest.raises(ValueError, match=r"^comparison artifact must not be a symlink$"):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_missing_file(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    cid = f"cmp_{'a' * 32}"
    with pytest.raises(ValueError, match=rf"^unknown comparison ID: {cid}$"):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_schema_or_id_mismatch(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"

    def mod(rec: dict[str, Any]) -> None:
        rec["schema_version"] = "wrong-comparison-schema"

    _update_comparison_record(target, mod)
    with pytest.raises(ValueError, match=r"^comparison schema/mode/ID mismatch$"):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_mode_mismatch(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"

    def mod(rec: dict[str, Any]) -> None:
        rec["identity"]["mode"] = "native-docx"

    _update_comparison_record(target, mod)
    with pytest.raises(ValueError, match=r"^comparison schema/mode/ID mismatch$"):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_options_threshold_mismatch(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(
        left, right, store=store, threshold=DEFAULT_HEADER_CONFIDENCE_THRESHOLD
    )
    with pytest.raises(ValueError, match=r"^pairing options mismatch$"):
        load_section_comparison(cid, store=store, threshold=0.5)


def test_load_section_comparison_rejects_asymmetric_explicit_runs(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    with pytest.raises(ValueError, match=r"^provide both ordered ingest runs or neither$"):
        load_section_comparison(cid, store=store, original_run=left, modified_run=None)


def test_load_section_comparison_rejects_invalid_run_locators(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"

    def mod(rec: dict[str, Any]) -> None:
        rec["runs"]["original"] = ""

    _update_comparison_record(target, mod)
    with pytest.raises(ValueError, match=r"^invalid ingest run locators$"):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_tampered_input_identity(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"

    def mod(rec: dict[str, Any]) -> None:
        rec["identity_sha256"] = "0" * 64

    _update_comparison_record(target, mod)
    with pytest.raises(
        ValueError, match=r"^comparison input tamper: source/segments/manifest/options mismatch$"
    ):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_tampered_decisions(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"

    def mod(rec: dict[str, Any]) -> None:
        rec["decisions"] = []

    _update_comparison_record(target, mod)
    with pytest.raises(
        ValueError, match=r"^comparison decisions tamper or unsupported engine version$"
    ):
        load_section_comparison(cid, store=store)


def test_load_section_comparison_rejects_invalid_artifact_structure(
    paired_runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = paired_runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    target = store / f"{cid}.json"

    def mod(rec: dict[str, Any]) -> None:
        del rec["identity"]

    _update_comparison_record(target, mod)
    with pytest.raises(ValueError, match=r"^invalid comparison artifact structure$"):
        load_section_comparison(cid, store=store)


# --- Group 5: _validate_docx ---


def test_validate_docx_rejects_missing_docx_members() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("unrelated.txt", b"plain")
    with pytest.raises(ValueError, match=r"^Not a DOCX package: sample\.docx$"):
        _validate_docx(buf.getvalue(), Path("sample.docx"))


def test_validate_docx_rejects_corrupted_crc_member() -> None:
    raw = bytearray(_create_valid_docx_bytes())
    idx = raw.find(b"content")
    assert idx != -1
    raw[idx] = ord("z")
    with pytest.raises(ValueError, match=r"^Corrupt DOCX package: sample\.docx$"):
        _validate_docx(bytes(raw), Path("sample.docx"))


def test_validate_docx_rejects_bad_zip_file() -> None:
    with pytest.raises(ValueError, match=r"^Not a DOCX package: sample\.docx$"):
        _validate_docx(b"NOT_A_ZIP_PACKAGE", Path("sample.docx"))


def test_validate_docx_rejects_zip_read_runtime_or_zlib_error() -> None:
    raw = bytearray(_create_valid_docx_bytes())
    cd_pos = raw.find(b"PK\x01\x02")
    cd_pos2 = raw.find(b"PK\x01\x02", cd_pos + 1)
    assert cd_pos2 != -1
    raw[cd_pos2 + 8] |= 0x1
    with pytest.raises(ValueError, match=r"^Corrupt DOCX package: sample\.docx$") as exc_info:
        _validate_docx(bytes(raw), Path("sample.docx"))
    assert isinstance(exc_info.value.__cause__, RuntimeError)


# --- Group 6: load_comparison_record ---


def test_load_comparison_record_rejects_invalid_id_format(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError, match=r"^Not a comparison ID: 'not-cmp-id'; expected cmp_<32 lowercase hex>$"
    ):
        load_comparison_record("not-cmp-id", store=tmp_path)


def test_load_comparison_record_rejects_missing_record_file(tmp_path: Path) -> None:
    cid = f"cmp_{'0' * 32}"
    with pytest.raises(ValueError, match=rf"^Unknown comparison ID: {cid}$"):
        load_comparison_record(cid, store=tmp_path)


def test_load_comparison_record_rejects_invalid_json_content(tmp_path: Path) -> None:
    cid = f"cmp_{'1' * 32}"
    (tmp_path / f"{cid}.json").write_text("not json content", encoding="utf-8")
    with pytest.raises(ValueError, match=rf"^Invalid comparison record: {cid}$"):
        load_comparison_record(cid, store=tmp_path)
