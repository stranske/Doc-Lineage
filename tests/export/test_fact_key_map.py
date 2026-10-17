"""Identity joins must not conflate variables, entities, or reporting periods."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from doc_lineage.export.fact_key_map import build_fact_key_map

FIXTURE = Path(__file__).parents[1] / "fixtures" / "fact_key_map" / "tracked_variables.json"


def test_map_joins_on_ontology_key():
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mapping = build_fact_key_map(records)
    assert mapping == {
        "var:alpha": {
            "ontology_key": "legal.withdrawal.notice_days",
            "entity_ref": "manager:alpha",
            "period": "2026-Q1",
        },
        "var:beta": {
            "ontology_key": "legal.withdrawal.notice_days",
            "entity_ref": "manager:beta",
            "period": "2026-Q2",
        },
    }


@pytest.mark.parametrize("field", ["variable_id", "ontology_key", "entity_ref"])
@pytest.mark.parametrize("value", [None, "", "   ", 3, []])
def test_rejects_incomplete_identity(field, value):
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    record[field] = value
    with pytest.raises(ValueError, match=field):
        build_fact_key_map([record])


def test_duplicate_ids_cannot_overwrite_a_different_join():
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    original = deepcopy(record)
    assert build_fact_key_map([record, record]) == build_fact_key_map([record])
    for field, value in [
        ("entity_ref", "manager:other"),
        ("ontology_key", "other.key"),
        ("period", "2025"),
    ]:
        changed = dict(record, **{field: value})
        with pytest.raises(ValueError, match="conflicting identity"):
            build_fact_key_map([record, changed])
    assert record == original


@pytest.mark.parametrize(
    "records, message",
    [([], "at least one"), ([None], "must be an object"), ([{}], "schema_version")],
)
def test_invalid_input(records, message):
    with pytest.raises(ValueError, match=message):
        build_fact_key_map(records)


def test_optional_period_and_canonical_entity():
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
    record.pop("period")
    assert "period" not in build_fact_key_map([record])[record["variable_id"]]
    record["entity_ref"] = "Display Name"
    with pytest.raises(ValueError, match="canonical entity"):
        build_fact_key_map([record])
    record["entity_ref"] = "manager:alpha"
    record["period"] = None
    with pytest.raises(ValueError, match="period"):
        build_fact_key_map([record])


def test_export_consumes_actual_pdf_extractor_output(tmp_path):
    from doc_lineage.export.fact_key_map import export_fact_key_map
    from doc_lineage.extract.variables import publish_variables
    from doc_lineage.ingest import ingest_document

    source = FIXTURE.parents[1] / "synthetic_lpa.pdf"
    ingest = ingest_document(
        source, output_dir=tmp_path / "ingest", allow_docling=False, ocr_enabled=False
    )
    publish_variables(ingest.output_dir, source, tmp_path / "extract", entity_ref="fund:alpha_iv")
    records_path = tmp_path / "extract" / "tracked-variables.json"
    (record,) = json.loads(records_path.read_text())
    manifest = export_fact_key_map(records_path, tmp_path / "map")
    assert manifest.is_file()
    mapping = json.loads((tmp_path / "map" / "fact_key_map.json").read_text())
    assert mapping[record["variable_id"]] == {
        "ontology_key": "legal.fees.management_rate",
        "entity_ref": "fund:alpha_iv",
    }
    assert record["evidence"]["excerpt"] == ingest.evidence[0]["excerpt"]
