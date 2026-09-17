"""``evidence-object/v1`` emission at the manifest boundary.

The parametrized schema-load pattern mirrors the backplane contract tests: the
schema is loaded from the synced contract file, never re-declared in the test,
so a contract change cannot pass silently here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from doc_lineage.emit import (
    EVIDENCE_DIRNAME,
    EVIDENCE_METHODS,
    EVIDENCE_SCHEMA_NAME,
    EVIDENCE_SCHEMA_VERSION,
    EXCERPT_MAX_CHARS,
    bound_excerpt,
    emit_evidence_object,
    evidence_id_for,
)
from doc_lineage.ingest import Segment, evidence_method_for, ingest_document
from doc_lineage.schema.validation import load_contract_schema

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_lpa.pdf"


def _span(text: str = "The Management Fee shall be 2.0% per annum.") -> Segment:
    return Segment(
        segment_id="abc123def456abcd-p0001-s0001",
        page=1,
        order=1,
        text=text,
        char_count=len(text),
        word_count=len(text.split()),
    )


def test_emitted_evidence_validates_against_schema(tmp_path: Path) -> None:
    """The named gate: every emitted evidence object conforms, on disk and in memory."""
    validator = Draft202012Validator(load_contract_schema(EVIDENCE_SCHEMA_NAME))

    direct = emit_evidence_object(_span(), source_id="sha256:deadbeef", method="text")
    validator.validate(direct)
    assert direct["schema_version"] == EVIDENCE_SCHEMA_VERSION

    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)
    assert result.evidence, "ingest must emit evidence for every segment"
    assert len(result.evidence) == len(result.segments)

    evidence_dir = tmp_path / EVIDENCE_DIRNAME
    for evidence in result.evidence:
        validator.validate(evidence)
        written = evidence_dir / f"{evidence['evidence_id']}.json"
        assert written.is_file()
        validator.validate(json.loads(written.read_text(encoding="utf-8")))


def test_emitted_evidence_carries_method_and_excerpt(tmp_path: Path) -> None:
    """``method`` and ``excerpt`` are the two fields the fleet omits; assert both."""
    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)

    segments_by_id = {segment.segment_id: segment for segment in result.segments}
    for evidence in result.evidence:
        assert evidence["method"] in EVIDENCE_METHODS
        assert evidence["method"] == evidence_method_for(result.backend)
        assert "excerpt" in evidence
        segment_id = evidence["fact_ref"].removeprefix("segment:")
        assert evidence["excerpt"] == segments_by_id[segment_id].text
        assert evidence["source_id"] == result.source_sha256


def test_evidence_is_referenced_from_the_run_manifest(tmp_path: Path) -> None:
    result = ingest_document(FIXTURE, output_dir=tmp_path, allow_docling=False)

    referenced = {
        artifact["path"]: artifact
        for artifact in result.manifest["artifacts"]
        if artifact["kind"] == "evidence"
    }
    assert len(referenced) == len(result.evidence)
    for evidence in result.evidence:
        artifact = referenced[f"{EVIDENCE_DIRNAME}/{evidence['evidence_id']}.json"]
        written = tmp_path / artifact["path"]
        assert artifact["bytes"] == written.stat().st_size


def test_evidence_ids_are_deterministic() -> None:
    first = emit_evidence_object(_span(), source_id="sha256:deadbeef", method="text")
    second = emit_evidence_object(_span(), source_id="sha256:deadbeef", method="text")
    other_method = emit_evidence_object(_span(), source_id="sha256:deadbeef", method="ocr")

    assert first["evidence_id"] == second["evidence_id"]
    assert first["evidence_id"] != other_method["evidence_id"]
    assert first["evidence_id"] == evidence_id_for(
        source_id="sha256:deadbeef",
        fact_ref=first["fact_ref"],
        method="text",
        excerpt=first["excerpt"],
    )


def test_long_excerpts_are_bounded_not_dropped() -> None:
    long_text = "clause " * 2000
    evidence = emit_evidence_object(_span(long_text), source_id="sha256:deadbeef", method="text")

    assert len(evidence["excerpt"]) == EXCERPT_MAX_CHARS
    assert evidence["excerpt"].endswith("...")
    Draft202012Validator(load_contract_schema(EVIDENCE_SCHEMA_NAME)).validate(evidence)


def test_bound_excerpt_leaves_short_text_untouched() -> None:
    assert bound_excerpt("short") == "short"


def test_unknown_method_is_rejected_before_validation() -> None:
    with pytest.raises(ValueError, match="method must be one of"):
        emit_evidence_object(_span(), source_id="sha256:deadbeef", method="guessed")


def test_empty_source_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="source_id must be a non-empty string"):
        emit_evidence_object(_span(), source_id="", method="text")


def test_locator_carries_the_page_pointer() -> None:
    evidence = emit_evidence_object(
        _span(), source_id="sha256:deadbeef", method="text", locator={"section": "6.1"}
    )

    assert evidence["locator"]["page"] == 1
    assert evidence["locator"]["order"] == 1
    assert evidence["locator"]["section"] == "6.1"
