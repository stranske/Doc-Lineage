"""Dependency-free acceptance gate for the materialized mutation catalog."""

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_and_manifest_are_complete() -> None:
    catalog = runpy.run_path(str(ROOT / "src/doc_lineage/mutations/catalog.py"))
    manifest = json.loads((ROOT / "tests/fixtures/mutations/manifest.json").read_text())
    catalog_ids = {spec.mutation_id for spec in catalog["MUTATION_SPECS"]}
    manifest_ids = {entry["mutation_id"] for entry in manifest["mutations"]}
    assert "management_fee_bump" in catalog_ids
    assert manifest_ids == catalog_ids
    for entry in manifest["mutations"]:
        assert (ROOT / entry["before"]).is_file()
        assert (ROOT / entry["after"]).is_file()
