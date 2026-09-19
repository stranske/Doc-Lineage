"""Verify the exported bytes and manifest through the public CLI."""

import hashlib
import json
from pathlib import Path

import pytest

from doc_lineage.cli import main
from doc_lineage.export.fact_key_map import export_fact_key_map
from doc_lineage.schema.validation import validate_contract_record

FIXTURE = Path(__file__).parents[1] / "fixtures" / "fact_key_map" / "tracked_variables.json"


def test_cli_publishes_manifest_and_real_mapping(tmp_path, capsys):
    output = tmp_path / "run"
    assert main(["export-fact-key-map", str(FIXTURE), "--output", str(output)]) == 0
    assert "manifest:" in capsys.readouterr().out
    manifest = json.loads((output / "artifact-manifest.json").read_text())
    validate_contract_record("artifact-manifest-v1", manifest)
    artifact = manifest["artifacts"][0]
    assert artifact["name"] == "artifact:fact_key_map.json"
    raw = (output / artifact["path"]).read_bytes()
    assert artifact["sha256"] == hashlib.sha256(raw).hexdigest()
    assert artifact["bytes"] == len(raw)
    assert json.loads(raw)["var:beta"]["entity_ref"] == "manager:beta"
    assert manifest["source"]["sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    second = tmp_path / "second"
    export_fact_key_map(FIXTURE, second)
    assert (second / "fact_key_map.json").read_bytes() == raw
    assert (second / "artifact-manifest.json").read_bytes() == (
        output / "artifact-manifest.json"
    ).read_bytes()


@pytest.mark.parametrize(
    "payload", ["not json", "{}", "[]", '[{"schema_version":"tracked-variable/v1"}]']
)
def test_invalid_input_publishes_nothing(tmp_path, capsys, payload):
    source = tmp_path / "input.json"
    source.write_text(payload)
    output = tmp_path / "run"
    assert main(["export-fact-key-map", str(source), "--output", str(output)]) == 1
    assert "export-fact-key-map:" in capsys.readouterr().err
    assert not output.exists()


def test_existing_run_is_preserved(tmp_path, capsys):
    output = tmp_path / "run"
    output.mkdir()
    manifest = output / "artifact-manifest.json"
    manifest.write_text("existing ingest manifest")
    assert main(["export-fact-key-map", str(FIXTURE), "--output", str(output)]) == 1
    assert "File exists" in capsys.readouterr().err
    assert manifest.read_text() == "existing ingest manifest"
    assert not (output / "fact_key_map.json").exists()
