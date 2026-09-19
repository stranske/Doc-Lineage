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


def _assert_complete(manifest_ids: set[str], catalog_ids: set[str]) -> None:
    # Independent fixture obligation prevents an empty catalog and regenerated
    # empty manifest from passing together.
    assert "management_fee_bump" in catalog_ids
    assert manifest_ids == catalog_ids


def test_all_catalog_mutations_materialized() -> None:
    """Every catalog mutation must appear in the generated manifest."""
    manifest = _load_manifest()
    _assert_complete(
        {entry["mutation_id"] for entry in manifest["mutations"]},
        {spec.mutation_id for spec in MUTATION_SPECS},
    )


@pytest.mark.parametrize("spec", MUTATION_SPECS, ids=[spec.mutation_id for spec in MUTATION_SPECS])
def test_catalog_change_class_detected(spec) -> None:
    before, after = _load_pair(spec.mutation_id)
    classes = detect_change_classes(before, after)
    assert spec.change_class in classes


def test_deliberate_break_skipping_catalog_mutation_fails_manifest_gate() -> None:
    """Removing even the sole mutation must fail the completeness gate."""
    catalog_ids = {spec.mutation_id for spec in MUTATION_SPECS}
    manifest_ids = {entry["mutation_id"] for entry in _load_manifest()["mutations"]}
    manifest_ids.remove("management_fee_bump")
    with pytest.raises(AssertionError):
        _assert_complete(manifest_ids, catalog_ids)
    with pytest.raises(AssertionError):
        _assert_complete(set(), set())


def test_generator_normalizes_paths_and_preserves_synthetic_identity(tmp_path, monkeypatch) -> None:
    from tools import generate_mutations

    monkeypatch.setattr(generate_mutations, "REPO_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    manifest = generate_mutations.generate(Path("generated"))
    entry = manifest["mutations"][0]
    after = load_segment_tree(tmp_path / entry["after"])
    before = load_segment_tree(tmp_path / entry["before"])
    assert after["source_sha256"] != before["source_sha256"]
    assert all(s["segment_id"].startswith(after["source_sha256"][:16]) for s in after["segments"])
    assert detect_change_classes(before, after) == ("gate_provision_change",)
    first = (tmp_path / entry["after"]).read_bytes()
    generate_mutations.generate(Path("generated"))
    assert (tmp_path / entry["after"]).read_bytes() == first
    outside = tmp_path / "outside" / "generated"
    monkeypatch.setattr(generate_mutations, "REPO_ROOT", tmp_path / "repo")
    with pytest.raises(ValueError):
        generate_mutations.generate(outside)
    assert not outside.exists()
