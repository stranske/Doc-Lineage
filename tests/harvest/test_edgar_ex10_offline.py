"""Offline SEC EX-10 harvest tests using recorded fixtures (no live SEC in CI)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from doc_lineage.harvest.edgar_ex10 import (
    MANIFEST_SCHEMA_VERSION,
    harvest_edgar_ex10,
    parse_ex10_exhibits,
)
from doc_lineage.schema.validation import load_contract_schema

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "harvest" / "edgar_ex10_filing.json"


def test_parse_ex10_fixture() -> None:
    """Named acceptance gate: recorded filing yields EX-10 exhibits only."""
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    exhibits = parse_ex10_exhibits(filing)

    assert len(exhibits) == 2
    assert [item.exhibit_type for item in exhibits] == ["EX-10.1", "EX-10.2"]
    assert exhibits[0].description == "Limited Partnership Agreement"
    assert exhibits[0].document_url.endswith("exhibit101lpa.htm")
    assert exhibits[0].accession_number == "0001067983-24-000045"


def test_harvest_writes_mirror_compatible_manifest(tmp_path: Path) -> None:
    result = harvest_edgar_ex10(
        "0001067983",
        tmp_path,
        fixture_path=FIXTURE,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    Draft202012Validator(load_contract_schema("artifact-manifest-v1")).validate(manifest)
    assert manifest["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert manifest["tool"] == "doc-lineage-harvest-edgar"
    assert len(manifest["artifacts"]) == 2
    provenance = manifest["artifacts"][0]["provenance"]
    assert provenance["schema_version"] == "document-mirror/v1"
    assert provenance["exhibit_type"] == "EX-10.1"


def test_parse_ex10_fixture_deliberate_break_empty_exhibits() -> None:
    """Deliberate-break gate: skipping EX-10 exhibits must fail the named test."""
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    filing["documents"] = [
        doc for doc in filing["documents"] if not str(doc.get("type", "")).startswith("EX-10")
    ]
    exhibits = parse_ex10_exhibits(filing)
    with pytest.raises(AssertionError):
        assert exhibits, "expected at least one EX-10 exhibit"
