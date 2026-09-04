"""The scaffold rename is load-bearing: CI installs the distribution by name and imports the package.

A leftover template name is not a cosmetic defect. It means the installed distribution and the
imported module disagree, which surfaces later as an import error in a workflow rather than here.
"""

from __future__ import annotations

import importlib
import pathlib
import tomllib


def test_distribution_and_package_names_are_not_the_template_placeholder() -> None:
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "doc-lineage"
    assert not pathlib.Path("src/my_project").exists()


def test_package_imports_and_exposes_a_version() -> None:
    mod = importlib.import_module("doc_lineage")
    assert mod.__version__
