"""Replay synthetic corpus ground truth through the comparison engine."""

import json
from pathlib import Path

from doc_lineage.compare.classify import (
    SegmentPair,
    classify_segment,
    load_class_catalog,
    load_tier_catalog,
)
from doc_lineage.compare.silence import apply_silence_invariant

CORPUS_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_corpus"


def test_replay_matches_ground_truth_manifest() -> None:
    manifest_path = CORPUS_ROOT / "ground_truth.json"
    assert manifest_path.exists(), "run tools/generate_synthetic_corpus.py before replay tests"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tiers = load_tier_catalog()
    classes = load_class_catalog()
    assert len(manifest["cases"]) > 0

    for case in manifest["cases"]:
        case_dir = CORPUS_ROOT / case["case_id"]
        prior = json.loads((case_dir / "prior_segments.json").read_text(encoding="utf-8"))
        current = json.loads((case_dir / "current_segments.json").read_text(encoding="utf-8"))
        section_ids = sorted(set(prior) | set(current))
        actual = {}
        for section_id in section_ids:
            pair = SegmentPair(
                section_id=section_id,
                prior_text=prior.get(section_id),
                current_text=current.get(section_id),
                explicit_removal=case["case_id"] == "explicit_drop_fixture",
            )
            classified = classify_segment(pair, tiers=tiers, classes=classes)
            prior_mentions = 1 if section_id in prior else 0
            current_mentions = 1 if section_id in current else 0
            classified = apply_silence_invariant(
                classified,
                prior_mentions=prior_mentions,
                current_mentions=current_mentions,
                explicit_removal=pair.explicit_removal,
            )
            actual[section_id] = {"change_type": classified.change_type, "tier": classified.tier}

        expected_map = {e["section_id"]: {"change_type": e["change_type"], "tier": e["tier"]}
                       for e in case["expected"]}
        assert actual == expected_map, f"Mismatch for case {case['case_id']}: actual={actual}, expected={expected_map}"
