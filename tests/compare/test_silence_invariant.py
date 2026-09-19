"""Silence-is-weak-evidence invariant tests."""

from inspect import getfile
from pathlib import Path

from doc_lineage.compare.classify import ClassifiedSegment
from doc_lineage.compare.silence import apply_silence_invariant


def test_absence_does_not_emit_dropped() -> None:
    """Bare absence (no explicit removal) must not classify as DROPPED."""
    # The deliberate-break gate transplants this test onto the base checkout.
    # A candidate installed editable in the runner must not supply missing base
    # modules and make that negative control pass against the wrong source tree.
    source_root = Path(__file__).resolve().parents[2] / "src"
    assert Path(getfile(apply_silence_invariant)).resolve().is_relative_to(source_root)
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


def test_explicit_removal_preserved_with_zero_current_mentions() -> None:
    """Explicit removal signal must preserve DROPPED even with zero current mentions."""
    classified = ClassifiedSegment(
        section_id="retired_clause",
        change_type="DROPPED",
        tier="T1",
        tier_label="decision-relevant",
        class_label="dropped",
        similarity=0.0,
    )
    result = apply_silence_invariant(
        classified, prior_mentions=1, current_mentions=0, explicit_removal=True
    )
    assert result.change_type == "DROPPED"


def test_explicit_removal_preserved_with_current_mentions() -> None:
    """Explicit removal signal must preserve DROPPED when current mentions exist."""
    classified = ClassifiedSegment(
        section_id="retired_clause",
        change_type="DROPPED",
        tier="T1",
        tier_label="decision-relevant",
        class_label="dropped",
        similarity=0.0,
    )
    result = apply_silence_invariant(
        classified, prior_mentions=1, current_mentions=1, explicit_removal=True
    )
    assert result.change_type == "DROPPED"


def test_non_dropped_with_prior_mentions_and_zero_current_becomes_unknown_absence() -> None:
    """Non-DROPPED segments with prior mentions and zero current become UNKNOWN_ABSENCE."""
    classified = ClassifiedSegment(
        section_id="some_segment",
        change_type="REVISED",
        tier="T1",
        tier_label="decision-relevant",
        class_label="revised",
        similarity=0.5,
    )
    result = apply_silence_invariant(classified, prior_mentions=1, current_mentions=0)
    assert result.change_type == "UNKNOWN_ABSENCE"
    assert result.tier == "T1"
    assert result.similarity == 0.5
