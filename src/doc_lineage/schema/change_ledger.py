"""Ledger row models with wire names matching the existing work-environment tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

from doc_lineage.schema._finite import require_finite_number
from doc_lineage.schema.enums import MaterialityTier, SegmentClassification, TextBasis

WIRE_FIELDS: dict[str, tuple[str, ...]] = {
    "change_ledger": (
        "doc_type",
        "transition",
        "canonical_section",
        "subsection",
        "item",
        "page_new",
        "change_type",
        "tier",
        "topic",
        "prior_text",
        "current_text",
    ),
    "continuity_ledger": (
        "doc_type",
        "transition",
        "canonical_section",
        "status",
        "words_current",
        "carry_forward_pct",
        "refresh_pct",
        "verbatim_words",
        "near_verbatim_words",
        "revised_words",
        "new_words",
        "dropped_words",
        "segments_verbatim",
        "segments_near",
        "segments_revised",
        "segments_new",
        "segments_dropped",
        "segments_cosmetic",
        "new_items",
        "dropped_items",
        "text_basis",
    ),
    "persistence_ledger": (
        "doc_type",
        "canonical_section",
        "item",
        "consecutive_years_unchanged",
        "first_seen",
        "last_seen",
        "words",
        "text",
    ),
    "stale_flag_ledger": (
        "doc_type",
        "canonical_section",
        "item",
        "consecutive_years_unchanged",
        "first_seen",
        "last_seen",
        "words",
        "text",
        "report_year",
        "flag",
    ),
    "section_crosswalk": (
        "doc_type",
        "year",
        "raw_section",
        "canonical_section",
        "words",
    ),
    "material_ledger": (
        "date",
        "tier",
        "theme",
        "category",
        "change",
        "From",
        "To",
    ),
}


def _validate_enum(value: str, enum_cls: type, field_name: str) -> str:
    try:
        enum_cls(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum_cls)
        raise ValueError(f"{field_name} must be one of {allowed}") from None
    return value


@dataclass(frozen=True, slots=True)
class ChangeLedgerRow:
    doc_type: str
    transition: str
    canonical_section: str
    subsection: str
    item: str
    page_new: int
    change_type: str
    tier: str
    topic: str
    prior_text: str
    current_text: str

    def __post_init__(self) -> None:
        _validate_enum(self.tier, MaterialityTier, "tier")

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> ChangeLedgerRow:
        return cls(**{field.name: payload[field.name] for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class ContinuityLedgerRow:
    doc_type: str
    transition: str
    canonical_section: str
    status: str
    words_current: int
    carry_forward_pct: float
    refresh_pct: float
    verbatim_words: int
    near_verbatim_words: int
    revised_words: int
    new_words: int
    dropped_words: int
    segments_verbatim: int
    segments_near: int
    segments_revised: int
    segments_new: int
    segments_dropped: int
    segments_cosmetic: int
    new_items: int
    dropped_items: int
    text_basis: str

    def __post_init__(self) -> None:
        for name in (
            "carry_forward_pct",
            "refresh_pct",
        ):
            object.__setattr__(self, name, require_finite_number(getattr(self, name), name))
        _validate_enum(self.text_basis, TextBasis, "text_basis")

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> ContinuityLedgerRow:
        return cls(**{field.name: payload[field.name] for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class PersistenceLedgerRow:
    doc_type: str
    canonical_section: str
    item: str
    consecutive_years_unchanged: int
    first_seen: str
    last_seen: str
    words: int
    text: str

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> PersistenceLedgerRow:
        return cls(**{field.name: payload[field.name] for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class StaleFlagLedgerRow:
    doc_type: str
    canonical_section: str
    item: str
    consecutive_years_unchanged: int
    first_seen: str
    last_seen: str
    words: int
    text: str
    report_year: int
    flag: str

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> StaleFlagLedgerRow:
        return cls(**{field.name: payload[field.name] for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class SectionCrosswalkRow:
    doc_type: str
    year: int
    raw_section: str
    canonical_section: str
    words: int

    def to_wire(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> SectionCrosswalkRow:
        return cls(**{field.name: payload[field.name] for field in fields(cls)})


@dataclass(frozen=True, slots=True)
class MaterialLedgerRow:
    date: str
    tier: str
    theme: str
    category: str
    change: str
    from_value: str = field(metadata={"wire_name": "From"})
    to_value: str = field(metadata={"wire_name": "To"})

    def __post_init__(self) -> None:
        _validate_enum(self.tier, MaterialityTier, "tier")

    def to_wire(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "tier": self.tier,
            "theme": self.theme,
            "category": self.category,
            "change": self.change,
            "From": self.from_value,
            "To": self.to_value,
        }

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> MaterialLedgerRow:
        return cls(
            date=payload["date"],
            tier=payload["tier"],
            theme=payload["theme"],
            category=payload["category"],
            change=payload["change"],
            from_value=payload["From"],
            to_value=payload["To"],
        )


def segment_classification_values() -> tuple[str, ...]:
    return tuple(member.value for member in SegmentClassification)
