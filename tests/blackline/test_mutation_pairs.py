"""Wire synthetic mutation pairs into the section-ID blackline engine (B2-005)."""

from __future__ import annotations

import json
from pathlib import Path

from doc_lineage.blackline import align_sections, build_section_tree
from doc_lineage.ingest import Segment

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "mutations"
MANIFEST_PATH = FIXTURES / "manifest.json"


def _load_pair(mutation_id: str) -> tuple[dict, dict]:
    pair_dir = FIXTURES / mutation_id
    before = json.loads((pair_dir / "before_segments.json").read_text(encoding="utf-8"))
    after = json.loads((pair_dir / "after_segments.json").read_text(encoding="utf-8"))
    return before, after


def test_mutation_pairs_align_by_section_id() -> None:
    """Mutation pairs must pair through the blackline engine without manual review."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest["mutations"]:
        before_payload, after_payload = _load_pair(entry["mutation_id"])
        before_segments = tuple(Segment(**item) for item in before_payload["segments"])
        after_segments = tuple(Segment(**item) for item in after_payload["segments"])
        doc_a = build_section_tree(before_segments, source_sha256=before_payload["source_sha256"])
        doc_b = build_section_tree(after_segments, source_sha256=after_payload["source_sha256"])
        pairs = align_sections(doc_a, doc_b)
        assert pairs, f"no section pairs for mutation {entry['mutation_id']}"
        assert all(pair.pairing_method == "section_id" for pair in pairs)
        changed = [
            pair
            for pair in pairs
            if pair.left is not None
            and pair.right is not None
            and pair.left.text != pair.right.text
        ]
        assert changed, f"mutation {entry['mutation_id']} must change at least one section"
