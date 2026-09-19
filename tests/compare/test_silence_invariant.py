"""Silence-is-weak-evidence invariant tests."""

from doc_lineage.compare.classify import ClassifiedSegment
from doc_lineage.compare.silence import apply_silence_invariant


def test_absence_does_not_emit_dropped() -> None:
    classified = ClassifiedSegment(
        section_id="legacy_clause",
        change_type="DROPPED",
        tier="T1",
        tier_label="decision-relevant",
        class_label="dropped",
        similarity=0.0,
    )
    result = apply_silence_invariant(classified, prior_mentions=1, current_mentions=0)
    assert result.change_type == "UNKNOWN_ABSENCE"
    assert result.change_type != "DROPPED"


def test_explicit_removal_can_remain_dropped_when_not_silent() -> None:
    classified = ClassifiedSegment(
        section_id="retired_clause",
        change_type="DROPPED",
        tier="T1",
        tier_label="decision-relevant",
        class_label="dropped",
        similarity=0.0,
    )
    result = apply_silence_invariant(classified, prior_mentions=1, current_mentions=1)
    assert result.change_type == "DROPPED"
