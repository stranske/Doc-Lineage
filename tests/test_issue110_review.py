"""Regression controls for comparison-record privacy, corrupt ZIPs and replay."""

import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from doc_lineage import blackline
from tests.export.test_docx_redline_golden import _docx

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence/issue-110"


def test_corrupt_deflate_has_clean_cli_error_without_record(tmp_path):
    archive = BytesIO()
    with (
        ZipFile(BytesIO(_docx("A legal source."))) as source,
        ZipFile(archive, "w", compression=ZIP_DEFLATED) as target,
    ):
        for member in source.infolist():
            target.writestr(member.filename, source.read(member.filename))
    payload = bytearray(archive.getvalue())
    with ZipFile(BytesIO(payload)) as package:
        member = package.getinfo("word/document.xml")
    name, extra = struct.unpack_from("<HH", payload, member.header_offset + 26)
    payload[member.header_offset + 30 + name + extra] = 0xFF
    broken, valid = tmp_path / "broken.docx", tmp_path / "valid.docx"
    broken.write_bytes(payload)
    valid.write_bytes(_docx("Other source."))
    store = tmp_path / "records"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "doc_lineage.cli",
            "create-comparison",
            "--original",
            str(broken),
            "--modified",
            str(valid),
            "--comparison-store",
            str(store),
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 1
    assert b"Corrupt DOCX package" in result.stderr, "CORRUPT_ZIP_ERROR_CONTRACT"
    assert b"Traceback" not in result.stderr
    assert not store.exists()
    assert broken.read_bytes() == payload


def test_new_records_are_private_and_exclusive_under_permissive_umask(tmp_path, monkeypatch):
    original, modified = tmp_path / "a.docx", tmp_path / "b.docx"
    original.write_bytes(_docx("Original."))
    modified.write_bytes(_docx("Modified."))
    store = tmp_path / "records"
    previous = os.umask(0)
    try:
        identity = blackline.write_comparison_record(original, modified, store=store)
    finally:
        os.umask(previous)
    record = store / f"{identity}.json"
    assert stat.S_IMODE(store.stat().st_mode) == 0o700, "PRIVATE_COMPARISON_STORE"
    assert stat.S_IMODE(record.stat().st_mode) == 0o600, "PRIVATE_COMPARISON_RECORD"
    before = record.read_bytes()
    monkeypatch.setattr(blackline, "uuid4", lambda: SimpleNamespace(hex=identity[4:]))
    with pytest.raises(FileExistsError):
        blackline.write_comparison_record(original, modified, store=store)
    assert record.read_bytes() == before


def _optimized(program, argument):
    return subprocess.run(
        [sys.executable, "-O", "-c", program, str(argument)],
        capture_output=True,
        check=False,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT)},
    )


def test_replay_hash_validation_survives_optimized_python(tmp_path):
    programs = re.findall(r"<<'PY'\n(.*?)\nPY", (EVIDENCE / "replay.sh").read_text(), re.S)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    record = {}
    for role in ("original", "modified"):
        content = _docx(role)
        (artifacts / f"{role}.docx").write_bytes(content)
        record[f"{role}_sha256"] = hashlib.sha256(content).hexdigest()
    (artifacts / "comparison-record.json").write_text(json.dumps(record))
    assert _optimized(programs[0], tmp_path).returncode == 0
    (artifacts / "original.docx").write_bytes(_docx("Changed valid document."))
    assert _optimized(programs[0], tmp_path).returncode != 0, "OPTIMIZED_REPLAY_HASH_CHECK"


def test_replay_revision_validation_survives_optimized_python(tmp_path):
    programs = re.findall(r"<<'PY'\n(.*?)\nPY", (EVIDENCE / "replay.sh").read_text(), re.S)
    original = EVIDENCE / "artifacts/redline.docx"
    assert _optimized(programs[1], original).returncode == 0
    changed = tmp_path / "wrong-revisions.docx"
    with ZipFile(original) as source, ZipFile(changed, "w") as target:
        for member in source.infolist():
            content = source.read(member.filename)
            if member.filename == "word/document.xml":
                assert b"five" in content
                content = content.replace(b"five", b"eleven")
            target.writestr(member, content)
    assert _optimized(programs[1], changed).returncode != 0, "OPTIMIZED_REPLAY_REVISION_CHECK"
