"""Muse belt canary: the marker file must exist with the exact marker line."""

from pathlib import Path

CANARY_PATH = Path(__file__).resolve().parents[1] / "docs" / "agents" / "MUSE_BELT_CANARY.md"
MARKER_LINE = "Muse belt canary: 2026-10-17"


def test_muse_belt_canary_file_has_marker() -> None:
    assert CANARY_PATH.exists(), f"canary file missing: {CANARY_PATH}"
    lines = CANARY_PATH.read_text(encoding="utf-8").splitlines()
    assert "# Muse belt canary" in lines
    assert MARKER_LINE in lines
