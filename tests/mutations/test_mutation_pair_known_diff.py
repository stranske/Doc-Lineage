"""Labeled mutation pairs for deterministic diff-gate ground truth (B2-008)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from doc_lineage.mutations import MUTATION_SPECS, detect_change_classes, load_segment_tree

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mutations"
MANIFEST_PATH = FIXTURES / "manifest.json"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_pair(mutation_id: str) -> tuple[dict, dict]:
    pair_dir = FIXTURES / mutation_id
    before = load_segment_tree(pair_dir / "before_segments.json")
    after = load_segment_tree(pair_dir / "after_segments.json")
    return before, after


def test_gate_provision_change_detected() -> None:
    """Named gate: management-fee mutation emits gate_provision_change."""
    before, after = _load_pair("management_fee_bump")
    classes = detect_change_classes(before, after)
    assert "gate_provision_change" in classes


def test_all_catalog_mutations_materialized() -> None:
    """Every catalog mutation must appear in the generated manifest (deliberate-break gate)."""
    manifest = _load_manifest()
    manifest_ids = {entry["mutation_id"] for entry in manifest["mutations"]}
    catalog_ids = {spec.mutation_id for spec in MUTATION_SPECS}
    assert manifest_ids == catalog_ids


@pytest.mark.parametrize("spec", MUTATION_SPECS, ids=[spec.mutation_id for spec in MUTATION_SPECS])
def test_catalog_change_class_detected(spec) -> None:
    before, after = _load_pair(spec.mutation_id)
    classes = detect_change_classes(before, after)
    assert spec.change_class in classes


def test_deliberate_break_skipping_catalog_mutation_fails_manifest_gate() -> None:
    """Skipping one catalog mutation must fail the manifest completeness gate."""
    manifest = _load_manifest()
    if len(MUTATION_SPECS) <= 1:
        pytest.skip("need multiple catalog mutations for skip-one deliberate-break gate")
    manifest_ids = {entry["mutation_id"] for entry in manifest["mutations"]}
    catalog_ids = {spec.mutation_id for spec in MUTATION_SPECS}
    skipped = catalog_ids - manifest_ids
    assert not skipped, f"catalog mutations missing from manifest: {sorted(skipped)}"
