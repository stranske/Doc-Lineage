from pathlib import Path


def test_muse_canary_file_has_marker() -> None:
    canary_path = Path(__file__).resolve().parent.parent / "docs" / "agents" / "MUSE_CANARY.md"

    assert canary_path.exists(), f"Muse canary file missing: {canary_path}"
    lines = canary_path.read_text(encoding="utf-8").splitlines()
    assert "Muse keepalive canary: 2026-10-16" in lines
