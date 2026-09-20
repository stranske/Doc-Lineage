"""The scaffold rename is load-bearing: CI installs the distribution by name and imports the package.

A leftover template name is not a cosmetic defect. It means the installed distribution and the
imported module disagree, which surfaces later as an import error in a workflow rather than here.
"""

from __future__ import annotations

import importlib
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tomllib


def test_distribution_and_package_names_are_not_the_template_placeholder() -> None:
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "doc-lineage"
    assert not pathlib.Path("src/my_project").exists()


def test_package_imports_and_exposes_a_version() -> None:
    mod = importlib.import_module("doc_lineage")
    assert mod.__version__


def test_sdist_includes_fact_key_map_fixture_with_export_tests(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        pathlib.Path(__file__).resolve().parents[1],
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".gitnexus",
            ".venv",
            "build",
            "dist",
            "*.egg-info",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ),
    )
    output = source / "dist"
    output.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from setuptools.build_meta import build_sdist; build_sdist('dist')",
        ],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    )

    archives = list(output.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        members = {"/".join(pathlib.PurePosixPath(name).parts[1:]) for name in archive.getnames()}
    assert "tests/export/test_fact_key_map.py" in members
    assert "tests/export/test_fact_key_map_cli.py" in members
    assert "tests/fixtures/fact_key_map/tracked_variables.json" in members
