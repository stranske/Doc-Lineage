"""Segment classification driven by versioned tier and class data files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from importlib.resources import files
from pathlib import Path
from typing import Any

_DATADIR = files("doc_lineage.compare.data")


@dataclass(frozen=True)
class TierDefinition:
    """One materiality tier loaded from ``segment_tiers.json``."""

    id: str
    label: str
    description: str


@dataclass(frozen=True)
class ClassDefinition:
    """One segment class loaded from ``segment_classes.json``."""

    id: str
    label: str
    description: str


@dataclass(frozen=True)
class TierCatalog:
    """Versioned tier metadata."""

    tiers: dict[str, TierDefinition]

    def label_for(self, tier_id: str) -> str:
        return self.tiers[tier_id].label


@dataclass(frozen=True)
class ClassCatalog:
    """Versioned segment-class metadata."""

    classes: dict[str, ClassDefinition]

    def label_for(self, class_id: str) -> str:
        return self.classes[class_id].label


@dataclass(frozen=True)
class SegmentPair:
    """Prior/current text for one comparable segment."""

    section_id: str
    prior_text: str | None
    current_text: str | None
    explicit_removal: bool = False


@dataclass(frozen=True)
class ClassifiedSegment:
    """Classification result for one segment pair."""

    section_id: str
    change_type: str
    tier: str
    tier_label: str
    class_label: str
    similarity: float


def _load_resource(resource_path: str) -> dict[str, Any]:
    """Load a JSON resource from the package or fallback to source checkout path."""
    try:
        ref = _DATADIR.joinpath(resource_path)
        text = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        module = Path(__file__).resolve()
        root = module.parents[3]
        if (
            module.parent != root / "src" / "doc_lineage"
            or not (root / "pyproject.toml").is_file()
        ):
            raise
        fallback = root / "src" / "doc_lineage" / "compare" / "data" / resource_path
        text = fallback.read_text(encoding="utf-8")
    return json.loads(text)


def load_tier_catalog(path: Path | None = None) -> TierCatalog:
    """Load tier definitions from ``segment_tiers.json`` packaged with doc_lineage.compare."""
    if path is not None:
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = _load_resource("segment_tiers.json")
    tiers = {
        key: TierDefinition(id=key, label=entry["label"], description=entry["description"])
        for key, entry in raw.items()
    }
    return TierCatalog(tiers=tiers)


def load_class_catalog(path: Path | None = None) -> ClassCatalog:
    """Load segment-class definitions from ``segment_classes.json`` packaged with doc_lineage.compare."""
    if path is not None:
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = _load_resource("segment_classes.json")
    classes = {
        key: ClassDefinition(id=key, label=entry["label"], description=entry["description"])
        for key, entry in raw.items()
    }
    return ClassCatalog(classes=classes)


def _similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _infer_change_type(pair: SegmentPair) -> str:
    prior = pair.prior_text or ""
    current = pair.current_text or ""
    if not prior and current:
        return "NEW"
    if prior and not current:
        if pair.explicit_removal:
            return "DROPPED"
        return "UNKNOWN_ABSENCE"
    if prior == current:
        return "VERBATIM"
    ratio = _similarity(prior, current)
    if ratio >= 0.85:
        return "NEAR_VERBATIM"
    return "REVISED"


def _infer_tier(change_type: str, similarity: float) -> str:
    if change_type == "NEW":
        return "T1"
    if change_type in {"VERBATIM", "NEAR_VERBATIM"}:
        return "T3"
    if change_type == "DROPPED":
        return "T1"
    if change_type == "UNKNOWN_ABSENCE":
        return "T2"
    if change_type == "REVISED":
        return "T1"
    return "T1"


def classify_segment(
    pair: SegmentPair,
    *,
    tiers: TierCatalog,
    classes: ClassCatalog,
) -> ClassifiedSegment:
    """Classify one segment pair using data-file tier and class catalogs."""
    prior = pair.prior_text or ""
    current = pair.current_text or ""
    similarity = _similarity(prior, current)
    change_type = _infer_change_type(pair)
    tier_id = _infer_tier(change_type, similarity)
    return ClassifiedSegment(
        section_id=pair.section_id,
        change_type=change_type,
        tier=tier_id,
        tier_label=tiers.label_for(tier_id),
        class_label=classes.label_for(change_type),
        similarity=similarity,
    )
