"""Segment comparison and classification."""

from doc_lineage.compare.classify import (
    ClassCatalog,
    ClassifiedSegment,
    SegmentPair,
    TierCatalog,
    classify_segment,
    load_class_catalog,
    load_tier_catalog,
)
from doc_lineage.compare.silence import apply_silence_invariant

__all__ = [
    "ClassCatalog",
    "ClassifiedSegment",
    "SegmentPair",
    "TierCatalog",
    "apply_silence_invariant",
    "classify_segment",
    "load_class_catalog",
    "load_tier_catalog",
]
