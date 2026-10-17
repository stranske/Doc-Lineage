"""Replay the unchanged real-PDF control and retain its genuine persisted files."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
from pathlib import Path

from doc_lineage.blackline import align_sections, build_section_tree, emit_lineage_edges_ndjson
from doc_lineage.ingest import Segment
from doc_lineage.mutations import detect_change_classes, load_segment_tree

ROOT = Path(__file__).resolve().parents[3]


def run(destination: Path) -> None:
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError("raw artifacts must be outside the checkout")
    destination.mkdir(parents=True, exist_ok=False)
    namespace = runpy.run_path(str(ROOT / "tests/blackline/test_section_id_pairing.py"))
    namespace["test_persisted_pdf_ingest_replays_existing_production_pairing"](destination)
    before, after = [
        load_segment_tree(destination / name / "segments.json") for name in ("before", "after")
    ]
    trees = [
        build_section_tree(
            tuple(Segment(**s) for s in payload["segments"]),
            source_sha256=payload["source_sha256"],
        )
        for payload in (before, after)
    ]
    pairs = align_sections(*trees)
    (destination / "lineage-edges.ndjson").write_text(emit_lineage_edges_ndjson(pairs) + "\n")
    result = {
        "sources": [p["source_sha256"] for p in (before, after)],
        "ids": [p.section_id for p in pairs],
        "methods": [p.pairing_method for p in pairs],
        "changed": [p.left.text != p.right.text for p in pairs],
        "classes": detect_change_classes(before, after),
        "test_sha256": hashlib.sha256(
            (ROOT / "tests/blackline/test_section_id_pairing.py").read_bytes()
        ).hexdigest(),
    }
    (destination / "replay.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
