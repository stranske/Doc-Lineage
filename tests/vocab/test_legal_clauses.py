"""Contract checks for the shared legal clause vocabulary."""

import json
import re
from pathlib import Path

from doc_lineage.vocab import load_legal_clauses

VOCAB_PATH = Path(__file__).resolve().parents[2] / "vocab" / "legal-clauses.json"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"Duplicate JSON map key: {key}"
        result[key] = value
    return result


def test_legal_clauses_minimum_keys_and_unique():
    data = json.loads(VOCAB_PATH.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    assert data["schema_version"] == "1.0.0"
    assert data["version"] == "1.0.0"
    assert data["non_authoritative"] is False
    clauses = data["clauses"]
    assert isinstance(clauses, dict)
    assert len(clauses) >= 20
    keys = [clause["ontology_key"] for clause in clauses.values()]
    assert len(keys) == len(set(keys)), "Duplicate ontology_key values"
    for map_key, clause in clauses.items():
        assert re.fullmatch(r"legal(?:\.[a-z][a-z0-9_]*){2,}", clause["ontology_key"])
        assert map_key == clause["ontology_key"]
        assert clause["source"] in data["sources"]
    assert "legal.withdrawal.notice_days" in clauses


def test_loader_is_independent_of_working_directory_and_returns_fresh_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expected = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    loaded = load_legal_clauses()
    assert loaded == expected
    loaded["clauses"].clear()
    assert load_legal_clauses() == expected


def test_loader_uses_bundled_resource(monkeypatch):
    monkeypatch.setattr("doc_lineage.vocab.Path.is_file", lambda self: False)
    monkeypatch.setattr("doc_lineage.vocab.files", lambda package: VOCAB_PATH.parent)
    assert load_legal_clauses() == json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
