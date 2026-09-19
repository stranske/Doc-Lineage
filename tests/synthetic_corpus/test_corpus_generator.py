"""Test the synthetic corpus generator directly."""

import json
import tempfile
from pathlib import Path

from tools.generate_synthetic_corpus import build_manifest, write_corpus


def test_write_corpus_generates_valid_manifest_and_files() -> None:
    """Exercise the generator: write_corpus produces manifest and paired files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        manifest_path = write_corpus(tmp_path)
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["version"] == 1
        assert len(manifest["cases"]) > 0

        for case in manifest["cases"]:
            case_dir = tmp_path / case["case_id"]
            assert case_dir.exists()
            assert (case_dir / "prior_segments.json").exists()
            assert (case_dir / "current_segments.json").exists()

            prior = json.loads((case_dir / "prior_segments.json").read_text(encoding="utf-8"))
            current = json.loads((case_dir / "current_segments.json").read_text(encoding="utf-8"))
            assert isinstance(prior, dict)
            assert isinstance(current, dict)


def test_build_manifest_returns_nonzero_cases() -> None:
    """Verify build_manifest returns a manifest with non-zero cases."""
    manifest = build_manifest()
    assert manifest["version"] == 1
    assert len(manifest["cases"]) > 0
    for case in manifest["cases"]:
        assert "case_id" in case
        assert "prior_segments" in case
        assert "current_segments" in case
        assert "expected" in case
        assert len(case["expected"]) > 0
