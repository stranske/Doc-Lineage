"""Section-ID pairing for the clause blackline engine (B2-005)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from doc_lineage.blackline import (
    DEFAULT_HEADER_CONFIDENCE_THRESHOLD,
    DocumentSections,
    Section,
    align_sections,
    build_section_tree,
    emit_lineage_edges_ndjson,
)
from doc_lineage.ingest import Segment

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "blackline"


@dataclass(frozen=True)
class _FixtureDoc:
    source_sha256: str
    segments: tuple[Segment, ...]


def _load_fixture(name: str) -> _FixtureDoc:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    segments = tuple(Segment(**entry) for entry in payload["segments"])
    return _FixtureDoc(source_sha256=payload["source_sha256"], segments=segments)


def test_pairs_by_section_id() -> None:
    """Named gate: numbered sections pair by stable section IDs on a golden pair."""
    before = _load_fixture("lpa_before_segments.json")
    after = _load_fixture("lpa_after_segments.json")
    doc_a = build_section_tree(before.segments, source_sha256=before.source_sha256)
    doc_b = build_section_tree(after.segments, source_sha256=after.source_sha256)

    pairs = align_sections(doc_a, doc_b)
    assert [pair.section_id for pair in pairs] == ["1", "2", "3", "4"]
    assert all(pair.pairing_method == "section_id" for pair in pairs)
    assert all(pair.left is not None and pair.right is not None for pair in pairs)
    assert pairs[0].left is not None and pairs[0].right is not None
    assert pairs[0].left.text != pairs[0].right.text
    assert pairs[1].left is not None and pairs[1].right is not None
    assert pairs[1].left.text == pairs[1].right.text

    ndjson = emit_lineage_edges_ndjson(pairs)
    assert ndjson.count('"schema_version": "lineage-edges/v1"') == 4


def test_low_header_confidence_fails_closed_to_manual_review() -> None:
    low_confidence = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=0.2,
        segment_ids=("seg-1",),
        text="1. MANAGEMENT FEE body",
    )
    doc_a = DocumentSections(source_sha256="left", sections=(low_confidence,))
    doc_b = DocumentSections(
        source_sha256="right",
        sections=(
            Section(
                section_id="1",
                title="MANAGEMENT FEE",
                header_confidence=1.0,
                segment_ids=("seg-2",),
                text="1. MANAGEMENT FEE body",
            ),
        ),
    )
    (pair,) = align_sections(doc_a, doc_b, threshold=DEFAULT_HEADER_CONFIDENCE_THRESHOLD)
    assert pair.pairing_method == "manual_review"


def test_deliberate_break_semantic_only_pairs_wrong_sections() -> None:
    """Semantic-only pairing must misalign IDs; section-ID pairing rejects that path."""
    before = _load_fixture("lpa_before_segments.json")
    after = _load_fixture("lpa_after_segments.json")
    doc_a = build_section_tree(before.segments, source_sha256=before.source_sha256)
    doc_b = build_section_tree(after.segments, source_sha256=after.source_sha256)

    id_pairs = align_sections(doc_a, doc_b)
    semantic_pairs = align_sections(doc_a, doc_b, force_semantic_only=True)
    with pytest.raises(AssertionError):
        assert all(
            id_pair.right is not None
            and semantic_pair.right is not None
            and id_pair.right.section_id == semantic_pair.right.section_id
            for id_pair, semantic_pair in zip(id_pairs, semantic_pairs, strict=True)
        )
