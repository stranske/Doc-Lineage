"""Segment classification driven by versioned tier and class data files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

_DATADIR = files("doc_lineage.compare").joinpath("data")


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
    tier: str


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
    default_tier: str = "T1"

    def label_for(self, class_id: str) -> str:
        return self.classes[class_id].label

    def tier_for(self, class_id: str) -> str:
        definition = self.classes.get(class_id)
        if definition is None:
            return self.default_tier
        return definition.tier


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
    """Load catalog JSON through the regular package so wheels and checkouts agree."""
    raw = json.loads(_DATADIR.joinpath(resource_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("catalog must be a JSON object")
    return cast(dict[str, Any], raw)


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


def _validate_class_tiers(classes: ClassCatalog, tiers: TierCatalog) -> None:
    for class_id, definition in classes.classes.items():
        if definition.tier not in tiers.tiers:
            raise ValueError(
                f"class {class_id!r} maps to unknown tier {definition.tier!r}; "
                f"expected one of {sorted(tiers.tiers)}"
            )


def load_class_catalog(
    path: Path | None = None,
    *,
    tiers: TierCatalog | None = None,
) -> ClassCatalog:
    """Load segment-class definitions from ``segment_classes.json`` packaged with doc_lineage.compare."""
    if path is not None:
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = _load_resource("segment_classes.json")
    classes = {
        key: ClassDefinition(
            id=key,
            label=entry["label"],
            description=entry["description"],
            tier=entry["tier"],
        )
        for key, entry in raw.items()
    }
    catalog = ClassCatalog(classes=classes)
    if tiers is not None:
        _validate_class_tiers(catalog, tiers)
    return catalog


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


def _infer_tier(change_type: str, classes: ClassCatalog) -> str:
    return classes.tier_for(change_type)


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
    tier_id = _infer_tier(change_type, classes)
    return ClassifiedSegment(
        section_id=pair.section_id,
        change_type=change_type,
        tier=tier_id,
        tier_label=tiers.label_for(tier_id),
        class_label=classes.label_for(change_type),
        similarity=similarity,
    )
