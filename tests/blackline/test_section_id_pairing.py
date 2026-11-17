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


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("invalid_side", ["left", "right"])
@pytest.mark.parametrize("threshold", [0.0, DEFAULT_HEADER_CONFIDENCE_THRESHOLD])
def test_non_finite_confidence_fails_closed_to_manual_review(
    confidence: float, invalid_side: str, threshold: float
) -> None:
    invalid_section = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=confidence,
        segment_ids=("seg-1",),
        text="1. MANAGEMENT FEE body",
    )
    valid_section = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=1.0,
        segment_ids=("seg-2",),
        text="1. MANAGEMENT FEE body",
    )
    doc_a = DocumentSections(
        source_sha256="left",
        sections=(invalid_section if invalid_side == "left" else valid_section,),
    )
    doc_b = DocumentSections(
        source_sha256="right",
        sections=(invalid_section if invalid_side == "right" else valid_section,),
    )
    (pair,) = align_sections(doc_a, doc_b, threshold=threshold)
    assert pair.pairing_method == "manual_review"
    assert pair.confidence == 0.0
    (edge,) = map(json.loads, emit_lineage_edges_ndjson([pair]).splitlines())
    assert edge["pairing_method"] == "manual_review"
    assert edge["confidence"] == 0.0


def test_finite_confidence_at_threshold_still_pairs_automatically() -> None:
    section = Section(
        section_id="1",
        title="MANAGEMENT FEE",
        header_confidence=0.0,
        segment_ids=("seg-1",),
        text="1. MANAGEMENT FEE body",
    )
    doc = DocumentSections(source_sha256="source", sections=(section,))

    (pair,) = align_sections(doc, doc, threshold=0.0)

    assert pair.pairing_method == "section_id"
    assert pair.confidence == 0.0


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
    from tests.blackline.test_comparison_run_cli import make_runs

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


@pytest.mark.parametrize("reorder_after", [False, True], ids=["same-order", "reordered-sections"])
def test_persisted_pdf_ingest_replays_existing_production_pairing(
    tmp_path: Path, reorder_after: bool
) -> None:
    """Issue 113 control: real PDF bytes survive restart into the existing caller.

    The fresh process uses mutations.detect's production JSON loader/composition.
    It does not implement the validated public comparison handoff owned by #112.
    """
    import hashlib
    import subprocess
    import sys

    from reportlab.pdfgen.canvas import Canvas

    for name, rate in (("before", "1.75"), ("after", "2.00")):
        source = tmp_path / f"{name}.pdf"
        canvas = Canvas(str(source), invariant=True)
        sections = [
            ("1. MANAGEMENT FEE", f"The annual management fee is {rate}%."),
            ("2. TERM", "The term is annual."),
        ]
        if name == "after" and reorder_after:
            sections.reverse()
        for header, body in sections:
            canvas.drawString(72, 720, header)
            canvas.drawString(72, 700, body)
            canvas.showPage()
        canvas.save()
        result = ingest_document(
            source, output_dir=tmp_path / name, allow_docling=False, ocr_enabled=False
        )
        assert result.backend == "offline-pdf-text"
        assert result.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
        for artifact in result.manifest["artifacts"]:
            data = (result.output_dir / artifact["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == artifact["sha256"]
            assert len(data) == artifact["bytes"]
        payload = json.loads(result.segments_path.read_text())
        for evidence in result.evidence:
            segment = next(
                s
                for s in payload["segments"]
                if evidence["fact_ref"] == f"segment:{s['segment_id']}"
            )
            assert evidence["source_id"] == payload["source_sha256"]
            assert evidence["locator"]["page"] == segment["page"] - 1
            assert evidence["excerpt"] == segment["text"]

    # No IngestResult crosses this boundary. The child only receives disk paths.
    code = """
import json, sys
from pathlib import Path
from doc_lineage.mutations import load_segment_tree, detect_change_classes
from doc_lineage.blackline import build_section_tree, align_sections, emit_lineage_edges_ndjson
from doc_lineage.ingest import Segment
before, after = [load_segment_tree(Path(p)) for p in sys.argv[1:]]
def tree(payload):
    return build_section_tree(tuple(Segment(**s) for s in payload['segments']),
                              source_sha256=payload['source_sha256'])
a, b = tree(before), tree(after)
pairs = align_sections(a, b)
print(json.dumps({'classes': detect_change_classes(before, after),
                  'ids': [p.section_id for p in pairs],
                  'methods': [p.pairing_method for p in pairs],
                  'changed': [p.left.text != p.right.text for p in pairs],
                  'left_segments': [list(p.left.segment_ids) for p in pairs],
                  'right_segments': [list(p.right.segment_ids) for p in pairs],
                  'edges': [json.loads(line) for line in emit_lineage_edges_ndjson(pairs).splitlines()],
                  'sources': [a.source_sha256, b.source_sha256]}))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(tmp_path / "before" / "segments.json"),
            str(tmp_path / "after" / "segments.json"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    replay = json.loads(child.stdout)
    assert replay["ids"] == ["1", "2"], "PERSISTED_INGEST_PAIRING_DISCONNECTED"
    assert replay["classes"] == ["gate_provision_change"], "PERSISTED_INGEST_CALLER_DISCONNECTED"
    assert replay["methods"] == ["section_id", "section_id"]
    assert replay["changed"] == [True, False]
    assert replay["sources"][0] != replay["sources"][1]
    persisted = json.loads((tmp_path / "before" / "segments.json").read_text())
    assert replay["left_segments"] == [[s["segment_id"]] for s in persisted["segments"]]
    revised = json.loads((tmp_path / "after" / "segments.json").read_text())
    right_segments = revised["segments"][::-1] if reorder_after else revised["segments"]
    assert replay["right_segments"] == [
        [s["segment_id"]] for s in right_segments
    ], "PERSISTED_INGEST_SECTION_MEMBERSHIP_DISCONNECTED"
    # Reordering changes the fee's page locator, not its section identity. Check
    # the actual published evidence rather than treating an edge as provenance.
    for name, payload, membership, fee_page in (
        ("before", persisted, replay["left_segments"], 0),
        ("after", revised, replay["right_segments"], int(reorder_after)),
    ):
        evidence_by_ref = {
            evidence["fact_ref"]: evidence
            for path in (tmp_path / name / "evidence").glob("*.json")
            for evidence in [json.loads(path.read_text())]
        }
        (fee_segment_id,) = membership[0]
        fee_evidence = evidence_by_ref[f"segment:{fee_segment_id}"]
        assert fee_evidence["source_id"] == payload["source_sha256"]
        assert fee_evidence["locator"]["page"] == fee_page
        assert "MANAGEMENT FEE" in fee_evidence["excerpt"]
    assert [e["section_id"] for e in replay["edges"]] == ["1", "2"]
    assert all(e["schema_version"] == "lineage-edges/v1" for e in replay["edges"])


def _segment(order: int, text: str, *, page: int = 1) -> Segment:
    return Segment(
        segment_id=f"sha-p{page:04d}-s{order:04d}",
        page=page,
        order=order,
        text=text,
        char_count=len(text),
        word_count=len(text.split()),
    )


def test_offline_synthetic_lpa_yields_sections_1_to_4(tmp_path: Path) -> None:
    """Issue #185 gate: inline PDF headings in flattened page segments become sections."""
    from doc_lineage.blackline import create_section_comparison, load_section_comparison

    source = FIXTURES.parent / "synthetic_lpa.pdf"
    result = ingest_document(
        source, output_dir=tmp_path / "lpa", allow_docling=False, ocr_enabled=False
    )
    assert result.backend == "offline-pdf-text"
    # The offline producer flattens several headings into one page segment.
    assert len(result.segments) < 4

    doc = build_section_tree(result.segments, source_sha256=result.source_sha256)
    assert [section.section_id for section in doc.sections] == ["1", "2", "3", "4"]
    assert [section.title for section in doc.sections] == [
        "MANAGEMENT FEE",
        "CARRIED INTEREST",
        "KEY PERSON EVENT",
        "TRANSFER RESTRICTIONS",
    ]
    section_3 = doc.sections[2]
    assert section_3.text.startswith("3. KEY PERSON EVENT")
    assert "4." not in section_3.text and "TRANSFER RESTRICTIONS" not in section_3.text
    assert doc.sections[3].text.startswith("4. TRANSFER RESTRICTIONS")
    assert "1.75%" in doc.sections[0].text and "2. CARRIED" not in doc.sections[0].text
    # Split sections keep membership of the source segment they came from.
    segment_ids = [segment.segment_id for segment in result.segments]
    for section in doc.sections:
        assert section.segment_ids and set(section.segment_ids) <= set(segment_ids)
    assert doc.sections[2].segment_ids == doc.sections[3].segment_ids

    store = tmp_path / "comparisons"
    run = tmp_path / "lpa"
    cid = create_section_comparison(run, run, store=store)
    record = load_section_comparison(cid, store=store)
    assert record["identity"]["options"]["engine"] == "section-id/v2"
    assert [d["section_id"] for d in record["decisions"]] == ["1", "2", "3", "4"]
    assert all(d["pairing_method"] == "section_id" for d in record["decisions"])
    # The title block before "1. MANAGEMENT FEE" is reported, not silently dropped.
    for role in ("original", "modified"):
        diagnostics = record["unassigned"][role]
        assert diagnostics["unassigned_char_count"] == doc.unassigned_char_count > 0
        assert diagnostics["unassigned_segment_ids"] == [result.segments[0].segment_id]


def test_headerless_preamble_is_counted_as_unassigned() -> None:
    preamble = "LIMITED PARTNERSHIP AGREEMENT of Example Fund, L.P."
    segments = (
        _segment(1, preamble),
        _segment(2, "Dated as of January 1. 1. FEES The fee is fixed."),
        _segment(3, "2. TERM The term is annual."),
    )
    doc = build_section_tree(segments, source_sha256="sha")
    assert [section.section_id for section in doc.sections] == ["1", "2"]
    assert doc.sections[0].text == "1. FEES The fee is fixed."
    assert doc.sections[0].segment_ids == ("sha-p0001-s0002",)
    assert doc.unassigned_char_count == len(preamble) + len("Dated as of January 1.")
    assert doc.unassigned_segment_ids == ("sha-p0001-s0001", "sha-p0001-s0002")

    no_preamble = build_section_tree(segments[2:], source_sha256="sha")
    assert no_preamble.unassigned_char_count == 0
    assert no_preamble.unassigned_segment_ids == ()


@pytest.mark.parametrize(
    "body",
    [
        "The fees include 1. MANAGEMENT FEE and 2. CARRIED INTEREST as defined.",
        "The fee is 1.75% of commitments. 2. the term is annual.",
        "Payments are due in 2 installments. 3. A notice is required.",
        "See clauses 2. TERM and 3. NOTICE below.",
    ],
)
def test_body_enumerations_do_not_split_sections(body: str) -> None:
    segments = (_segment(1, f"1. FEES {body}"),)
    doc = build_section_tree(segments, source_sha256="sha")
    assert [section.section_id for section in doc.sections] == ["1"]
    assert doc.sections[0].text == f"1. FEES {body}"
    assert doc.unassigned_char_count == 0


def test_line_start_heading_splits_and_shared_segment_keeps_both_memberships() -> None:
    # Line-start branch: no sentence end precedes "2. TERM", only a newline.
    segments = (
        _segment(1, "1. FEES The fee is fixed\n2. TERM The term runs"),
        _segment(2, "until year end. 3. NOTICE Notices are written."),
    )
    doc = build_section_tree(segments, source_sha256="sha")
    assert [section.section_id for section in doc.sections] == ["1", "2", "3"]
    assert doc.sections[0].text == "1. FEES The fee is fixed"
    # Section 2 continues into segment 2 before section 3 starts inside it.
    assert doc.sections[1].segment_ids == ("sha-p0001-s0001", "sha-p0001-s0002")
    assert doc.sections[1].text == "2. TERM The term runs\nuntil year end."
    assert doc.sections[2].segment_ids == ("sha-p0001-s0002",)
    assert doc.unassigned_char_count == 0 and doc.unassigned_segment_ids == ()


def test_section_id_v1_comparison_records_are_rejected(tmp_path: Path) -> None:
    from tests.blackline.test_comparison_run_cli import make_runs

    from doc_lineage.blackline import (
        _canonical_bytes,
        create_section_comparison,
        load_section_comparison,
    )
    from doc_lineage.identity import sha256_bytes

    left, right = make_runs(tmp_path)
    store = tmp_path / "comparisons"
    cid = create_section_comparison(left, right, store=store)
    path = store / f"{cid}.json"
    record = json.loads(path.read_bytes())
    # A well-formed legacy record: v1 engine, no unassigned diagnostics.
    record.pop("record_sha256")
    record.pop("unassigned")
    record["identity"]["options"]["engine"] = "section-id/v1"
    record["identity_sha256"] = sha256_bytes(_canonical_bytes(record["identity"]))
    record["record_sha256"] = sha256_bytes(_canonical_bytes(record))
    path.write_bytes(_canonical_bytes(record))
    with pytest.raises(ValueError, match="section-id/v1 is retired"):
        load_section_comparison(cid, store=store)


def test_unassigned_diagnostics_tamper_is_rejected(tmp_path: Path) -> None:
    from tests.blackline.test_comparison_run_cli import make_runs

    from doc_lineage.blackline import (
        _canonical_bytes,
        create_section_comparison,
        load_section_comparison,
    )
    from doc_lineage.identity import sha256_bytes

    left, right = make_runs(tmp_path)
    store = tmp_path / "comparisons"
    cid = create_section_comparison(left, right, store=store)
    path = store / f"{cid}.json"
    record = json.loads(path.read_bytes())
    assert record["unassigned"]["original"] == {
        "unassigned_char_count": 0,
        "unassigned_segment_ids": [],
    }
    record.pop("record_sha256")
    record["unassigned"]["original"]["unassigned_char_count"] = 7
    record["record_sha256"] = sha256_bytes(_canonical_bytes(record))
    path.write_bytes(_canonical_bytes(record))
    with pytest.raises(ValueError, match="unassigned-text diagnostics tamper"):
        load_section_comparison(cid, store=store)


def test_pair_sections_cli_warns_on_unassigned_text(tmp_path: Path) -> None:
    from tests.blackline.test_comparison_run_cli import cli

    run = tmp_path / "lpa"
    ingest_document(
        FIXTURES.parent / "synthetic_lpa.pdf",
        output_dir=run,
        allow_docling=False,
        ocr_enabled=False,
    )
    result = cli("pair-sections", run, run, "--store", tmp_path / "store", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("cmp_")
    assert "warning: original run has" in result.stderr
    assert "warning: modified run has" in result.stderr
