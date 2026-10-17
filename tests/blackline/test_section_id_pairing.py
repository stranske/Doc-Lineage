"""Section-ID pairing for the clause blackline engine (B2-005)."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from doc_lineage.blackline import (
    DEFAULT_HEADER_CONFIDENCE_THRESHOLD,
    DocumentSections,
    Section,
    SectionPair,
    align_sections,
    build_section_tree,
    emit_lineage_edges_ndjson,
)
from doc_lineage.ingest import Segment, ingest_document

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "blackline"


@dataclass(frozen=True)
class _FixtureDoc:
    source_sha256: str
    segments: tuple[Segment, ...]


def _load_fixture(name: str) -> _FixtureDoc:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    segments = tuple(Segment(**entry) for entry in payload["segments"])
    return _FixtureDoc(source_sha256=payload["source_sha256"], segments=segments)


def _misaligned_pairs_for_test(
    doc_a: DocumentSections,
    doc_b: DocumentSections,
) -> list[SectionPair]:
    """Test-only fault injection: pair by position with reversed right order."""
    left_sections = list(doc_a.sections)
    right_sections = list(doc_b.sections)
    ordered_ids = sorted(
        {section.section_id for section in left_sections}
        | {section.section_id for section in right_sections},
        key=lambda value: int(value),
    )
    pairs: list[SectionPair] = []
    for index, section_id in enumerate(ordered_ids):
        left = left_sections[index] if index < len(left_sections) else None
        right = right_sections[-(index + 1)] if index < len(right_sections) else None
        pairs.append(
            SectionPair(
                section_id=section_id,
                left=left,
                right=right,
                pairing_method="manual_review",
                confidence=0.0,
            )
        )
    return pairs


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


def test_header_only_segment_starts_section() -> None:
    """A header-only segment such as '1. MANAGEMENT FEE' still opens a section."""
    segments = (
        Segment(
            segment_id="sha-p0001-s0001",
            page=1,
            order=1,
            text="1. MANAGEMENT FEE",
            char_count=17,
            word_count=3,
        ),
        Segment(
            segment_id="sha-p0001-s0002",
            page=1,
            order=2,
            text="The Partnership shall pay the General Partner.",
            char_count=46,
            word_count=8,
        ),
    )
    doc = build_section_tree(segments, source_sha256="sha")
    assert len(doc.sections) == 1
    assert doc.sections[0].section_id == "1"
    assert doc.sections[0].title == "MANAGEMENT FEE"
    assert "General Partner" in doc.sections[0].text


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


def test_non_finite_confidence_fails_closed_to_manual_review() -> None:
    nan_confidence = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=math.nan,
        segment_ids=("seg-1",),
        text="1. MANAGEMENT FEE body",
    )
    doc_a = DocumentSections(source_sha256="left", sections=(nan_confidence,))
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
    (pair,) = align_sections(doc_a, doc_b)
    assert pair.pairing_method == "manual_review"
    assert math.isfinite(pair.confidence)


def test_one_sided_section_id_emits_manual_review() -> None:
    """Added or deleted sections must not pair as high-confidence section_id."""
    section = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=1.0,
        segment_ids=("seg-1",),
        text="1. MANAGEMENT FEE body",
    )
    doc_with_section = DocumentSections(source_sha256="left", sections=(section,))
    doc_empty = DocumentSections(source_sha256="right", sections=())

    (deleted_pair,) = align_sections(doc_with_section, doc_empty)
    assert deleted_pair.pairing_method == "manual_review"
    assert deleted_pair.left is not None
    assert deleted_pair.right is None

    (added_pair,) = align_sections(doc_empty, doc_with_section)
    assert added_pair.pairing_method == "manual_review"
    assert added_pair.left is None
    assert added_pair.right is not None


def test_non_finite_threshold_fails_closed_to_manual_review() -> None:
    section = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=1.0,
        segment_ids=("seg-1",),
        text="1. MANAGEMENT FEE body",
    )
    doc_a = DocumentSections(source_sha256="left", sections=(section,))
    doc_b = DocumentSections(source_sha256="right", sections=(section,))

    (pair,) = align_sections(doc_a, doc_b, threshold=math.nan)
    assert pair.pairing_method == "manual_review"


def test_duplicate_section_ids_emit_manual_review_pairs() -> None:
    duplicate_left = (
        Section(
            section_id="1",
            title="MANAGEMENT FEE",
            header_confidence=1.0,
            segment_ids=("seg-1",),
            text="1. MANAGEMENT FEE first",
        ),
        Section(
            section_id="1",
            title="MANAGEMENT FEE",
            header_confidence=1.0,
            segment_ids=("seg-2",),
            text="1. MANAGEMENT FEE duplicate",
        ),
    )
    doc_a = DocumentSections(source_sha256="left", sections=duplicate_left)
    doc_b = DocumentSections(
        source_sha256="right",
        sections=(
            Section(
                section_id="1",
                title="MANAGEMENT FEE",
                header_confidence=1.0,
                segment_ids=("seg-3",),
                text="1. MANAGEMENT FEE right",
            ),
        ),
    )
    pairs = align_sections(doc_a, doc_b)
    assert len(pairs) == 2
    assert all(pair.section_id == "1" for pair in pairs)
    assert all(pair.pairing_method == "manual_review" for pair in pairs)


def test_deliberate_break_semantic_only_pairs_wrong_sections() -> None:
    """Semantic-only pairing must misalign IDs; section-ID pairing rejects that path."""
    before = _load_fixture("lpa_before_segments.json")
    after = _load_fixture("lpa_after_segments.json")
    doc_a = build_section_tree(before.segments, source_sha256=before.source_sha256)
    doc_b = build_section_tree(after.segments, source_sha256=after.source_sha256)

    id_pairs = align_sections(doc_a, doc_b)
    semantic_pairs = _misaligned_pairs_for_test(doc_a, doc_b)
    with pytest.raises(AssertionError):
        assert all(
            id_pair.right is not None
            and semantic_pair.right is not None
            and id_pair.right.section_id == semantic_pair.right.section_id
            for id_pair, semantic_pair in zip(id_pairs, semantic_pairs, strict=True)
        )


@pytest.mark.parametrize("preamble", [False, True])
def test_docling_items_survive_ingest_and_section_pairing(
    tmp_path: Path,
    docling_items: Callable[[Sequence[tuple[int, str]]], None],
    preamble: bool,
) -> None:
    source = FIXTURES.parent / "synthetic_lpa.pdf"
    items = [(1, "Agreement")] if preamble else []
    items += [
        (1, "1. FEES"),
        (1, "The fee is fixed."),
        (1, "2. TERM"),
        (2, "The term is annual."),
    ]
    docling_items(items)
    before = ingest_document(source, output_dir=tmp_path / "before")
    repeat = ingest_document(source, output_dir=tmp_path / "repeat")
    assert before.backend == "docling"
    assert before.segments == repeat.segments
    assert [(segment.page, segment.text) for segment in before.segments] == items
    assert [segment.segment_id for segment in before.segments] == [
        f"{before.source_sha256[:16]}-p{page:04d}-s{order:04d}"
        for order, (page, _text) in enumerate(items, start=1)
    ]
    # Persisted ingest artifacts retain the item boundaries, not only in-memory output.
    persisted = json.loads(before.segments_path.read_text())["segments"]
    assert [(segment["page"], segment["text"]) for segment in persisted] == items
    for artifact in before.manifest["artifacts"]:
        from doc_lineage.identity import sha256_bytes

        payload = (before.output_dir / artifact["path"]).read_bytes()
        assert sha256_bytes(payload) == artifact["sha256"]
        assert len(payload) == artifact["bytes"]

    doc_a = build_section_tree(before.segments, source_sha256=before.source_sha256)
    assert [section.section_id for section in doc_a.sections] == ["1", "2"]
    assert doc_a.sections[0].text == "1. FEES\nThe fee is fixed."
    assert doc_a.sections[1].text == "2. TERM\nThe term is annual."
    assert doc_a.sections[1].segment_ids[-1] == before.segments[-1].segment_id
    assert before.segments[-1].page == 2

    docling_items([*items[:-1], (2, "The term is monthly.")])
    after = ingest_document(source, output_dir=tmp_path / "after")
    doc_b = build_section_tree(after.segments, source_sha256=after.source_sha256)
    pairs = align_sections(doc_a, doc_b)
    assert [pair.section_id for pair in pairs] == ["1", "2"]
    assert all(pair.pairing_method == "section_id" for pair in pairs)
    assert pairs[0].left is not None and pairs[0].right is not None
    assert pairs[1].left is not None and pairs[1].right is not None
    assert pairs[0].left.text == pairs[0].right.text
    assert pairs[1].left.text != pairs[1].right.text


def test_persisted_section_pairing_binds_ordered_inputs_and_replays(tmp_path: Path) -> None:
    """Issue #112 production gate: validated independent ingests feed the real engine."""
    from test_comparison_run_cli import make_runs

    from doc_lineage.blackline import create_section_comparison, load_section_comparison

    left, right = make_runs(tmp_path)
    store = tmp_path / "comparisons"
    cid = create_section_comparison(left, right, store=store)
    record = load_section_comparison(cid, store=store)
    assert [d["section_id"] for d in record["decisions"]] == [
        "1",
        "2",
        "2",
        "3",
        "4",
    ], "PERSISTED_SECTION_PAIRING_MUST_CALL_EXISTING_ENGINE"
    assert record["decisions"][0]["pairing_method"] == "section_id"
    assert all(d["pairing_method"] == "manual_review" for d in record["decisions"][1:])
    assert (
        record["identity"]["original"]["source_sha256"]
        != record["identity"]["modified"]["source_sha256"]
    )
    with pytest.raises(ValueError, match="source order mismatch"):
        load_section_comparison(cid, store=store, original_run=right, modified_run=left)
