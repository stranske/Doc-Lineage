"""Synthetic mutation harness for CI ground truth (B2-008)."""

from doc_lineage.mutations.catalog import MUTATION_SPECS, MutationSpec
from doc_lineage.mutations.detect import detect_change_classes, load_segment_tree

__all__ = [
    "MUTATION_SPECS",
    "MutationSpec",
    "detect_change_classes",
    "load_segment_tree",
]
