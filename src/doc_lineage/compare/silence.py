"""Silence-is-weak-evidence invariant for segment classification."""

from __future__ import annotations

from doc_lineage.compare.classify import ClassifiedSegment


def apply_silence_invariant(
    classified: ClassifiedSegment,
    *,
    prior_mentions: int,
    current_mentions: int = 0,
) -> ClassifiedSegment:
    """Refuse to map bare absence to ``DROPPED`` without an explicit removal signal.

    When a segment was present in the prior document but has zero mentions in the
    current document, absence alone is weak evidence and must not auto-emit
    ``DROPPED``.
    """
    if classified.change_type == "DROPPED" and prior_mentions > 0 and current_mentions == 0:
        return ClassifiedSegment(
            section_id=classified.section_id,
            change_type="UNKNOWN_ABSENCE",
            tier=classified.tier,
            tier_label=classified.tier_label,
            class_label="unknown absence",
            similarity=classified.similarity,
        )
    if (
        classified.change_type != "DROPPED"
        and prior_mentions > 0
        and current_mentions == 0
        and classified.change_type not in {"UNKNOWN_ABSENCE"}
    ):
        return ClassifiedSegment(
            section_id=classified.section_id,
            change_type="UNKNOWN_ABSENCE",
            tier=classified.tier,
            tier_label=classified.tier_label,
            class_label="unknown absence",
            similarity=classified.similarity,
        )
    return classified
