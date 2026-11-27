"""Repository-level checks for generated and deliberately vendored trees."""

import argparse
import re
import subprocess
from pathlib import Path

import pytest

from doc_lineage.cli import build_parser

REPO_ROOT = Path(__file__).resolve().parents[1]
STALE_ENGINE_SENTENCE = "remains to be implemented"
STATUS_PREFIX = "**Status:**"
# Pre-#115 status claim used by the deliberate-break gate.
STALE_STATUS_PARAGRAPH = (
    "**Status:** created 2026-09-04 as part of the Research Program 2026-09 "
    "(see `stranske/Ready` → `research-program/`). Scope, architecture and first "
    "issues arrive from research briefs R1 (legal-document decomposition) and R2 "
    "(consultant-report diffing). The initial legal clause vocabulary and Python "
    "loader are available; the document processing engine remains to be implemented."
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_generated_dirs_untracked_and_vendored_preserved() -> None:
    root_modules = _git("ls-files", "node_modules")
    assert root_modules.returncode == 0
    assert not root_modules.stdout.strip(), "root node_modules must not be tracked"

    vendored_modules = _git(
        "ls-files",
        "--error-unmatch",
        "--",
        ".github/scripts/node_modules/minimatch/package.json",
    )
    assert vendored_modules.returncode == 0
    assert vendored_modules.stdout.strip(), "vendored minimatch tree must remain tracked"

    root_ignore = _git("check-ignore", "-q", "node_modules/probe.js")
    assert root_ignore.returncode == 0, "root node_modules must be ignored"

    vendored_ignore = _git(
        "check-ignore",
        "-q",
        "--no-index",
        ".github/scripts/node_modules/minimatch/package.json",
    )
    assert vendored_ignore.returncode == 1, "vendored minimatch tree must not be ignored"


def _cli_subcommand_names() -> set[str]:
    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("build_parser() has no subcommands")


def _readme_status_paragraph(readme: str) -> str:
    """Return the Status block from **Status:** through the line before the next ## heading."""
    lines = readme.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(STATUS_PREFIX)), None)
    if start is None:
        raise AssertionError("README.md missing **Status:** paragraph")
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return "\n".join(lines[start:end]).rstrip()


def test_readme_mentions_every_cli_subcommand() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    status = _readme_status_paragraph(readme)
    assert STALE_ENGINE_SENTENCE not in status
    assert STALE_ENGINE_SENTENCE not in readme
    assert "shipped" in status
    assert "partial" in status
    assert "](" in status, "README status paragraph must include markdown links"
    for name in sorted(_cli_subcommand_names()):
        assert (
            name in status
        ), f"README status paragraph must mention doc-lineage subcommand `{name}`"


def _prose_only_status_paragraph() -> str:
    """Valid-input control twin: every CLI name present, but no per-capability status/links."""
    names = ", ".join(f"`{name}`" for name in sorted(_cli_subcommand_names()))
    return (
        "**Status:** created 2026-09-04 as part of the Research Program 2026-09 "
        "(see `stranske/Ready` → `research-program/`). Scope and architecture follow "
        "research briefs R1 and R2. The offline engine under `src/doc_lineage/` covers "
        f"{names}. Gaps are described in later sections."
    )


def _assert_status_break_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    original = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    status = _readme_status_paragraph(original)
    broken = original.replace(status, replacement, 1)
    assert broken != original

    candidate = tmp_path / "README.md"
    candidate.write_text(broken, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)

    with pytest.raises(AssertionError):
        test_readme_mentions_every_cli_subcommand()


def test_deliberate_break_stale_readme_status_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-#115 unimplemented-engine paragraph must fail the status hygiene gate."""
    assert STALE_ENGINE_SENTENCE in STALE_STATUS_PARAGRAPH
    _assert_status_break_fails(tmp_path, monkeypatch, STALE_STATUS_PARAGRAPH)


def test_deliberate_break_prose_only_status_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI names alone are not enough: shipped/partial markers and markdown links are required."""
    prose = _prose_only_status_paragraph()
    assert STALE_ENGINE_SENTENCE not in prose
    for name in _cli_subcommand_names():
        assert name in prose
    assert "shipped" not in prose
    assert "partial" not in prose
    assert "](" not in prose
    _assert_status_break_fails(tmp_path, monkeypatch, prose)


# Pre-correction README sentence used by the DOCX-by-ID deliberate-break gate.
STALE_DOCX_BY_ID_SENTENCE = (
    "it does not classify text differences, confirm supersession or complete native\n"
    "DOCX export by ID. Issue #15 remains pending that separate acceptance."
)
NO_DOCX_LIMIT = "section pairing produces no docx output"
DOCX_BY_ID_DOCS = {
    "README.md": "](#comparison-records)",
    "docs/section-pairing.md": "](../README.md#comparison-records)",
}


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text)
    return re.split(r"(?<=[.!?])\s+", flat)


def test_docx_by_id_not_described_as_pending() -> None:
    """Export by comparison ID shipped; docs must not call it pending (issue #15)."""
    for relative, link in DOCX_BY_ID_DOCS.items():
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        lowered = text.lower()
        flat = re.sub(r"\s+", " ", lowered)
        assert (
            "issue #15 remains pending" not in flat
        ), f"{relative} contains stale 'issue #15 remains pending' claim"
        assert (
            "issue #15 completion remain pending" not in flat
        ), f"{relative} contains stale 'issue #15 completion remain pending' claim"
        for sentence in _sentences(lowered):
            assert not (
                "#15" in sentence and "pending" in sentence
            ), f"{relative} describes issue #15 as pending: {sentence!r}"
        assert NO_DOCX_LIMIT in flat, f"{relative} must state section pairing yields no DOCX"
        assert link in text, f"{relative} must link to the Comparison records section"


def test_deliberate_break_docx_by_id_pending_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restoring the old 'Issue #15 remains pending' sentence must fail the gate."""
    original = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    broken = original.replace(
        "Section pairing produces no DOCX output.",
        f"Section pairing produces no DOCX output. {STALE_DOCX_BY_ID_SENTENCE}",
        1,
    )
    assert broken != original

    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(broken, encoding="utf-8")
    (tmp_path / "docs" / "section-pairing.md").write_text(
        (REPO_ROOT / "docs" / "section-pairing.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)

    with pytest.raises(AssertionError, match=r"issue #15.*pending"):
        test_docx_by_id_not_described_as_pending()
