"""Wire-name and validation gates for adopted ledger schemas."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from doc_lineage.schema import (
    ChangeLedgerRow,
    ContinuityLedgerRow,
    MaterialLedgerRow,
    PersistenceLedgerRow,
    load_schema,
    validate_record,
)
from doc_lineage.schema.change_ledger import WIRE_FIELDS
from doc_lineage.schema.enums import MaterialityTier, SegmentClassification

FIXTURES = Path(__file__).parent / "fixtures" / "schema"


def _schema_property_names(schema_name: str) -> set[str]:
    schema = load_schema(schema_name)
    return set(schema["properties"].keys())


@pytest.mark.parametrize(
    ("schema_name", "expected_fields"),
    sorted(WIRE_FIELDS.items()),
)
def test_wire_names_match_json_schema(schema_name: str, expected_fields: tuple[str, ...]) -> None:
    assert tuple(sorted(_schema_property_names(schema_name))) == tuple(sorted(expected_fields))


def test_segment_vocabulary_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="COSMETIC_ONLY"):
        SegmentClassification("COSMETIC_ONLY")


def test_materiality_tier_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="T4"):
        MaterialityTier("T4")


def test_validate_record_rejects_non_finite_percentages() -> None:
    payload = {
        "doc_type": "consultant_report",
        "transition": "2024_to_2025",
        "canonical_section": "overview",
        "status": "REVISED",
        "words_current": 10,
        "carry_forward_pct": math.nan,
        "refresh_pct": 0.0,
        "verbatim_words": 1,
        "near_verbatim_words": 1,
        "revised_words": 1,
        "new_words": 1,
        "dropped_words": 0,
        "segments_verbatim": 1,
        "segments_near": 0,
        "segments_revised": 0,
        "segments_new": 0,
        "segments_dropped": 0,
        "segments_cosmetic": 0,
        "new_items": 0,
        "dropped_items": 0,
        "text_basis": "native",
    }
    with pytest.raises(ValueError, match="finite"):
        validate_record("continuity_ledger", payload)


def test_non_finite_percentage_rejected() -> None:
    payload = {
        "doc_type": "consultant_report",
        "transition": "2024_to_2025",
        "canonical_section": "overview",
        "status": "REVISED",
        "words_current": 10,
        "carry_forward_pct": math.inf,
        "refresh_pct": 0.0,
        "verbatim_words": 1,
        "near_verbatim_words": 1,
        "revised_words": 1,
        "new_words": 1,
        "dropped_words": 0,
        "segments_verbatim": 1,
        "segments_near": 0,
        "segments_revised": 0,
        "segments_new": 0,
        "segments_dropped": 0,
        "segments_cosmetic": 0,
        "new_items": 0,
        "dropped_items": 0,
        "text_basis": "native",
    }
    with pytest.raises(ValueError, match="finite"):
        ContinuityLedgerRow.from_wire(payload)


def test_consultant_report_fixture_validates() -> None:
    bundle = json.loads(
        (FIXTURES / "consultant_report_transition.json").read_text(encoding="utf-8")
    )
    validate_record("change_ledger", bundle["change_ledger"])
    validate_record("continuity_ledger", bundle["continuity_ledger"])
    ChangeLedgerRow.from_wire(bundle["change_ledger"])
    ContinuityLedgerRow.from_wire(bundle["continuity_ledger"])


def test_legal_filing_fixture_validates() -> None:
    bundle = json.loads((FIXTURES / "legal_filing_transition.json").read_text(encoding="utf-8"))
    validate_record("change_ledger", bundle["change_ledger"])
    validate_record("material_ledger", bundle["material_ledger"])
    ChangeLedgerRow.from_wire(bundle["change_ledger"])
    MaterialLedgerRow.from_wire(bundle["material_ledger"])


def test_persistence_ledger_fixture_validates() -> None:
    payload = {
        "doc_type": "consultant_report",
        "canonical_section": "portfolio_overview",
        "item": "equity_weight",
        "consecutive_years_unchanged": 3,
        "first_seen": "2022",
        "last_seen": "2025",
        "words": 42,
        "text": "unchanged allocation language",
    }
    validate_record("persistence_ledger", payload)
    PersistenceLedgerRow.from_wire(payload)


def test_persistence_ledger_rejects_extra_fields() -> None:
    payload = {
        "doc_type": "consultant_report",
        "canonical_section": "portfolio_overview",
        "item": "equity_weight",
        "consecutive_years_unchanged": 3,
        "first_seen": "2022",
        "last_seen": "2025",
        "words": 42,
        "text": "unchanged allocation language",
        "unexpected": True,
    }
    with pytest.raises(ValidationError):
        validate_record("persistence_ledger", payload)


def test_material_ledger_round_trip_preserves_from_to_wire_names() -> None:
    row = MaterialLedgerRow(
        date="2024-03-15",
        tier="T1",
        theme="risk_controls",
        category="leverage",
        change="maximum leverage reduced",
        from_value="2.0x",
        to_value="1.5x",
    )
    wire = row.to_wire()
    assert set(wire) == {"date", "tier", "theme", "category", "change", "From", "To"}
    restored = MaterialLedgerRow.from_wire(wire)
    assert restored.to_wire() == wire


def test_deliberate_break_carry_forward_pct_name_fails_wire_name_gate() -> None:
    """Renaming carry_forward_pct must fail the schema-derived wire-name test."""
    schema = load_schema("continuity_ledger")
    broken = dict(schema)
    broken["properties"] = dict(schema["properties"])
    broken["properties"]["carryforward_pct"] = broken["properties"].pop("carry_forward_pct")
    broken["required"] = [
        name if name != "carry_forward_pct" else "carryforward_pct" for name in schema["required"]
    ]
    assert "carry_forward_pct" not in broken["properties"]
    assert "carryforward_pct" in broken["properties"]
    with pytest.raises(AssertionError):
        assert tuple(sorted(broken["properties"])) == tuple(
            sorted(WIRE_FIELDS["continuity_ledger"])
        )
