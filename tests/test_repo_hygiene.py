"""Repository-level checks for generated and deliberately vendored trees."""

import argparse
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


def test_deliberate_break_stale_readme_status_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep the deliberate-break acceptance gate reproducible without editing README.md."""
    original = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    status = _readme_status_paragraph(original)
    broken = original.replace(status, STALE_STATUS_PARAGRAPH, 1)
    assert broken != original
    assert STALE_ENGINE_SENTENCE in broken

    candidate = tmp_path / "README.md"
    candidate.write_text(broken, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)

    with pytest.raises(AssertionError):
        test_readme_mentions_every_cli_subcommand()
