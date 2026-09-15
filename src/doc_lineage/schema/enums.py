"""Closed vocabularies adopted from the existing work-environment tools."""

from enum import Enum


class SegmentClassification(str, Enum):
    """Segment tier labels used by both comparison tools."""

    VERBATIM = "VERBATIM"
    NEAR_VERBATIM = "NEAR_VERBATIM"
    REVISED = "REVISED"
    NEW = "NEW"
    DROPPED = "DROPPED"


class MaterialityTier(str, Enum):
    """Materiality tiers: T1 decision-relevant, T2 factual refresh, T3 cosmetic."""

    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class TextBasis(str, Enum):
    """Whether continuity percentages were computed from native, OCR, or mixed text."""

    NATIVE = "native"
    OCR = "ocr"
    MIXED = "mixed"
