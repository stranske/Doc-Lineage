"""Canary: Cursor belt path creates docs/agents/CURSOR_BELT_CANARY.md with marker."""

from pathlib import Path

MARKER = "Cursor belt canary: 2026-10-17"
CANARY_PATH = Path(__file__).resolve().parents[1] / "docs" / "agents" / "CURSOR_BELT_CANARY.md"


def test_cursor_belt_canary_file_has_marker() -> None:
    assert CANARY_PATH.is_file(), f"missing canary file: {CANARY_PATH}"
    content = CANARY_PATH.read_text(encoding="utf-8")
    assert MARKER in content.splitlines(), f"marker line missing from {CANARY_PATH}"
