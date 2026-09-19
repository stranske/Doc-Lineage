"""Offline SEC EX-10 harvest tests using recorded fixtures (no live SEC in CI)."""

from __future__ import annotations

import hashlib
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
FIXTURE_DIR = FIXTURE.parent


def test_parse_ex10_fixture() -> None:
    """Named acceptance gate: recorded filing yields EX-10 exhibits only."""
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    exhibits = parse_ex10_exhibits(filing)

    assert len(exhibits) == 2
    assert [item.exhibit_type for item in exhibits] == ["EX-10.1", "EX-10.2"]
    assert exhibits[0].description == "Limited Partnership Agreement"
    assert exhibits[0].document_url.endswith("exhibit101lpa.htm")
    assert exhibits[0].accession_number == "0001067983-24-000045"
    assert exhibits[0].doc_type_id() == "edgar_ex10_lpa"
    assert exhibits[1].doc_type_id() == "edgar_ex10_side_letter"


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
    assert manifest["artifacts"][0]["doc_type_id"] == "edgar_ex10_lpa"
    assert manifest["artifacts"][1]["doc_type_id"] == "edgar_ex10_side_letter"

    for artifact in manifest["artifacts"]:
        artifact_path = tmp_path / artifact["path"]
        assert artifact_path.is_file()
        content = artifact_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        assert artifact["sha256"] == digest
        assert artifact["content_sha256"] == digest
        assert artifact["bytes"] == len(content)
        assert artifact["bytes"] > 0
        assert artifact["media_type"] == "text/html"


def test_harvest_rejects_invalid_accession_in_fixture(tmp_path: Path) -> None:
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    filing["accession_number"] = "../escape"
    bad_fixture = tmp_path / "bad_filing.json"
    bad_fixture.write_text(json.dumps(filing), encoding="utf-8")
    for name in ("exhibit101lpa.htm", "exhibit102sideletter.htm"):
        (tmp_path / name).write_bytes((FIXTURE_DIR / name).read_bytes())

    with pytest.raises(ValueError, match="accession_number"):
        harvest_edgar_ex10("0001067983", tmp_path / "out", fixture_path=bad_fixture)


def test_harvest_rejects_fixture_path_traversal(tmp_path: Path) -> None:
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    filing["documents"][1]["document_url"] = "https://example.test/Archives/..\\secret"
    bad_fixture = tmp_path / "traversal_filing.json"
    bad_fixture.write_text(json.dumps(filing), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid fixture local name"):
        harvest_edgar_ex10("0001067983", tmp_path / "out", fixture_path=bad_fixture)


@pytest.mark.parametrize("field", ["sequence", "description", "document_url"])
def test_parse_ex10_rejects_null_fields(field: str) -> None:
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    filing["documents"][1][field] = None
    with pytest.raises(ValueError, match="sequence, description, and document_url"):
        parse_ex10_exhibits(filing)


def test_parse_ex10_fixture_deliberate_break_empty_exhibits() -> None:
    """Deliberate-break gate: skipping EX-10 exhibits must fail the named test."""
    filing = json.loads(FIXTURE.read_text(encoding="utf-8"))
    filing["documents"] = [
        doc for doc in filing["documents"] if not str(doc.get("type", "")).startswith("EX-10")
    ]
    exhibits = parse_ex10_exhibits(filing)
    with pytest.raises(AssertionError):
        assert exhibits, "expected at least one EX-10 exhibit"
