"""Bounded fallback controls; these do not simulate Windows ACL guarantees."""

import os
import stat
from pathlib import Path

import pytest

from doc_lineage import persistence
from doc_lineage.ingest import ingest_document


def test_missing_posix_capabilities_warn_and_retain_complete_ingest(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "fixtures/synthetic_lpa.pdf"
    monkeypatch.delattr(persistence.os, "O_DIRECTORY")
    monkeypatch.delattr(persistence.os, "fchmod")
    with pytest.warns(RuntimeWarning) as observed:
        result = ingest_document(source, output_dir=tmp_path / "run", allow_docling=False)
    messages = [str(w.message) for w in observed]
    assert any(
        "directory durability is unsupported" in w for w in messages
    ), "MISSING_DIRECTORY_CAPABILITY_IS_EXPLICIT"
    assert any(
        "owner-only privacy is unverified" in w for w in messages
    ), "MISSING_PRIVACY_CAPABILITY_IS_EXPLICIT"
    assert (
        result.manifest_path.parent / f"source-{result.source_sha256}.bin"
    ).read_bytes() == source.read_bytes()
    # The fallback actually chmods on this POSIX host; this is not a Windows claim.
    assert stat.S_IMODE(result.segments_path.stat().st_mode) == 0o600


def test_missing_fchmod_restricts_existing_file_before_write(tmp_path, monkeypatch):
    path = tmp_path / "sensitive.json"
    path.write_bytes(b"old bytes")
    path.chmod(0o666)
    monkeypatch.delattr(persistence.os, "fchmod")
    chmod = os.chmod

    def check_before_write(target, mode):
        assert path.read_bytes() == b"old bytes", "FALLBACK_CHMOD_PRECEDES_WRITE"
        chmod(target, mode)

    monkeypatch.setattr(persistence.os, "chmod", check_before_write)
    with pytest.warns(RuntimeWarning, match="privacy is unverified"):
        persistence.write_private(path, b"new bytes")
    assert path.read_bytes() == b"new bytes"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_fallback_chmod_failure_preserves_existing_bytes(tmp_path, monkeypatch):
    path = tmp_path / "sensitive.json"
    path.write_bytes(b"retained")
    monkeypatch.delattr(persistence.os, "fchmod")

    def fail(*args):
        raise OSError("chmod denied")

    monkeypatch.setattr(persistence.os, "chmod", fail)
    with pytest.warns(RuntimeWarning), pytest.raises(OSError, match="chmod denied"):
        persistence.write_private(path, b"must not write")
    assert path.read_bytes() == b"retained"
