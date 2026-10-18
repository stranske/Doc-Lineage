"""Verifier canary: marker file must exist with the expected line."""

from pathlib import Path

MARKER_LINE = "Verifier canary: 2026-10-18"


def test_verifier_canary_file_has_marker() -> None:
    canary_path = Path(__file__).resolve().parents[1] / "docs" / "agents" / "VERIFIER_CANARY.md"
    assert canary_path.is_file(), f"missing canary file: {canary_path}"
    lines = canary_path.read_text(encoding="utf-8").splitlines()
    assert MARKER_LINE in lines, f"missing exact marker line in {canary_path}"
