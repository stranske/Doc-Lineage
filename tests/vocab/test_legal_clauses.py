"""Contract checks for the shared legal clause vocabulary."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from doc_lineage.vocab import load_legal_clauses

VOCAB_PATH = Path(__file__).resolve().parents[2] / "vocab" / "legal-clauses.json"


def _assert_vocabulary(data):
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


def test_legal_clauses_minimum_keys_and_unique():
    _assert_vocabulary(load_legal_clauses())


def test_loader_is_independent_of_working_directory_and_returns_fresh_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expected = load_legal_clauses()
    _assert_vocabulary(expected)
    loaded = load_legal_clauses()
    assert loaded == expected
    loaded["clauses"].clear()
    assert load_legal_clauses() == expected


def test_loader_uses_bundled_resource(monkeypatch):
    _assert_vocabulary(load_legal_clauses())
    monkeypatch.setattr("doc_lineage.vocab.files", lambda package: VOCAB_PATH.parent)
    assert load_legal_clauses() == json.loads(VOCAB_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("failure", ["dependency", "installed_layout", "missing_project"])
def test_loader_does_not_hide_resource_import_failures(tmp_path, monkeypatch, failure):
    """Only a source checkout with an absent resource package may use the fallback."""
    _assert_vocabulary(load_legal_clauses())
    root = tmp_path / "project"
    package_dir = root / ("site-packages" if failure == "installed_layout" else "src")
    module = package_dir / "doc_lineage" / "vocab.py"
    module.parent.mkdir(parents=True)
    module.touch()
    if failure != "missing_project":
        (root / "pyproject.toml").touch()
    decoy = root / "vocab" / "legal-clauses.json"
    decoy.parent.mkdir()
    decoy.write_text('{"wrong": true}', encoding="utf-8")
    missing = "resource_dependency" if failure == "dependency" else "doc_lineage._vocab"
    error = ModuleNotFoundError(f"No module named {missing!r}", name=missing)

    def unavailable_resource(package):
        raise error

    monkeypatch.setattr("doc_lineage.vocab.__file__", str(module))
    monkeypatch.setattr("doc_lineage.vocab.files", unavailable_resource)
    with pytest.raises(ModuleNotFoundError) as caught:
        load_legal_clauses()
    assert caught.value is error


def test_installed_wheel_loads_bundled_vocabulary_despite_adjacent_decoy(tmp_path):
    """Exercise the actual build configuration and resource lookup outside the checkout."""
    root = VOCAB_PATH.parent.parent
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(root / name, checkout / name)
    shutil.copytree(root / "src" / "doc_lineage", checkout / "src" / "doc_lineage")
    shutil.copytree(root / "vocab", checkout / "vocab")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from setuptools.build_meta import build_wheel; build_wheel(sys.argv[1])",
            str(wheels),
        ],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    )
    installed = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--target",
            str(installed),
            str(next(wheels.glob("*.whl"))),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    shutil.rmtree(checkout)
    expected = load_legal_clauses()
    _assert_vocabulary(expected)
    for with_decoy in (False, True):
        if with_decoy:
            decoy = tmp_path / "vocab" / "legal-clauses.json"
            decoy.parent.mkdir()
            decoy.write_text('{"wrong": true}', encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import sys, json; sys.path.insert(0, sys.argv[1]); "
                "from doc_lineage.vocab import load_legal_clauses; "
                "print(json.dumps(load_legal_clauses()))",
                str(installed),
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("duplicate_map_key", [False, True], ids=["ontology_value", "map_key"])
def test_uniqueness_gate_rejects_duplicates(tmp_path, monkeypatch, duplicate_map_key):
    """Keep the deliberate-break acceptance gate reproducible without editing source data."""
    data = load_legal_clauses()
    _assert_vocabulary(data)
    clauses = list(data["clauses"].values())
    first_key = clauses[0]["ontology_key"]
    second_key = clauses[1]["ontology_key"]
    clauses[1]["ontology_key"] = first_key
    text = json.dumps(data)
    if duplicate_map_key:
        text = text.replace(json.dumps(second_key), json.dumps(first_key), 1)
    broken_vocab = tmp_path / "legal-clauses.json"
    broken_vocab.write_text(text, encoding="utf-8")
    monkeypatch.setattr("doc_lineage.vocab.files", lambda package: broken_vocab.parent)
    message = "Duplicate JSON map key" if duplicate_map_key else "Duplicate ontology_key values"
    error = ValueError if duplicate_map_key else AssertionError
    with pytest.raises(error, match=message):
        test_legal_clauses_minimum_keys_and_unique()


@pytest.mark.parametrize("count", [19, 20], ids=["below_minimum", "at_minimum"])
def test_minimum_count_gate_boundary(tmp_path, monkeypatch, count):
    data = load_legal_clauses()
    _assert_vocabulary(data)
    required_key = "legal.withdrawal.notice_days"
    other_keys = [key for key in data["clauses"] if key != required_key]
    keys = [required_key, *other_keys[: count - 1]]
    data["clauses"] = {key: data["clauses"][key] for key in keys}
    candidate = tmp_path / "legal-clauses.json"
    candidate.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("doc_lineage.vocab.files", lambda package: candidate.parent)
    if count < 20:
        with pytest.raises(AssertionError):
            test_legal_clauses_minimum_keys_and_unique()
    else:
        test_legal_clauses_minimum_keys_and_unique()


@pytest.mark.parametrize(
    "invalid_key",
    [
        "legal.notice_days",
        "other.withdrawal.notice_days",
        "legal.Withdrawal.notice_days",
        "legal.withdrawal.notice-days",
        "legal.withdrawal.1notice",
        "legal.withdrawal.notice_days\n",
    ],
)
def test_ontology_key_pattern_gate_rejects_invalid_keys(tmp_path, monkeypatch, invalid_key):
    data = load_legal_clauses()
    _assert_vocabulary(data)
    original_key = next(key for key in data["clauses"] if key != "legal.withdrawal.notice_days")
    clause = data["clauses"].pop(original_key)
    clause["ontology_key"] = invalid_key
    data["clauses"][invalid_key] = clause
    candidate = tmp_path / "legal-clauses.json"
    candidate.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("doc_lineage.vocab.files", lambda package: candidate.parent)
    with pytest.raises(AssertionError):
        test_legal_clauses_minimum_keys_and_unique()
