"""Canary: Cursor keepalive marker file must exist with the expected line."""

from pathlib import Path

CANARY_MARKER = "Cursor keepalive canary: 2026-10-15"


def test_cursor_canary_file_has_marker() -> None:
    canary_path = Path(__file__).resolve().parents[1] / "docs" / "agents" / "CURSOR_CANARY.md"
    assert canary_path.is_file(), f"missing canary file: {canary_path}"
    contents = canary_path.read_text(encoding="utf-8")
    assert CANARY_MARKER in contents.splitlines()
