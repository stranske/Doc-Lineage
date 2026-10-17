"""Revision-bound audit observations, not tests requiring permanent API absence.

Run with PYTHONPATH=src python docs/evidence/issue-113/probe_base.py OUTSIDE_DIR.
The production tree must match the reviewed base. This makes missing-transition
observations reproducible without constraining implementations after #128/#129.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from doc_lineage.blackline import align_sections, build_section_tree, emit_lineage_edges_ndjson
from doc_lineage.cli import main
from doc_lineage.export.fact_key_map import export_fact_key_map
from doc_lineage.ingest import Segment, ingest_document
from doc_lineage.mutations import detect_change_classes, load_segment_tree
from doc_lineage.render import resolve_triple_link
from doc_lineage.vocab import load_legal_clauses

BASE = "45971929b534d953e1c56ffb42b4bdfc3fd4b994"
ROOT = Path(__file__).resolve().parents[3]


def observe(label, call):
    """Capture exact behavior; absence/failure is data, never a future invariant."""
    try:
        value = call()
        return {"probe": label, "returned": value}
    except (Exception, SystemExit) as exc:
        return {"probe": label, "exception": type(exc).__name__, "message": str(exc)}


def run(destination: Path) -> None:
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError("raw artifacts must be outside the checkout")
    # Compare every production byte, also detecting new/deleted modules.
    changed = subprocess.check_output(["git", "diff", BASE, "--", "src"], cwd=ROOT)
    if changed or subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "src"], cwd=ROOT
    ):
        raise ValueError("production differs from the reviewed base; observations need a new audit")
    destination.mkdir(parents=True, exist_ok=False)
    result = ingest_document(
        ROOT / "tests/fixtures/synthetic_lpa.pdf",
        output_dir=destination / "ingest",
        allow_docling=False,
        ocr_enabled=False,
        git_sha=BASE,
        created_at="2026-10-17T00:00:00Z",
    )
    payload = load_segment_tree(result.segments_path)
    tree = build_section_tree(
        tuple(Segment(**s) for s in payload["segments"]), source_sha256=payload["source_sha256"]
    )
    controls = {
        "base": BASE,
        "original_sha256": hashlib.sha256(result.source_path.read_bytes()).hexdigest(),
        "backend": result.backend,
        "segment_pages": [s["page"] for s in payload["segments"]],
        "segment_texts": [s["text"] for s in payload["segments"]],
        "section_ids": [s.section_id for s in tree.sections],
        "identical_reload_pairing": [p.section_id for p in align_sections(tree, tree)],
        "edges": emit_lineage_edges_ndjson(align_sections(tree, tree)),
        "evidence": list(result.evidence),
    }
    changed_fee = copy.deepcopy(payload)
    for segment in changed_fee["segments"]:
        segment["text"] = segment["text"].replace("1.75%", "2.00%")
    observations = [
        observe(
            "persisted path directly into documented section builder",
            lambda: build_section_tree(result.segments_path, source_sha256=result.source_sha256),
        ),
        observe("public persisted pairing", lambda: main(["pair-sections", "--help"])),
        observe("public source-to-claims", lambda: main(["extract-variables", "--help"])),
        observe(
            "actual published segments into existing tracked-variable consumer",
            lambda: str(export_fact_key_map(result.segments_path, destination / "segments-map")),
        ),
        observe(
            "actual published evidence into existing navigation consumer",
            lambda: resolve_triple_link(result.evidence[0]),
        ),
        observe(
            "original PDF inline numbered clauses into actual mutation caller",
            lambda: detect_change_classes(payload, changed_fee),
        ),
    ]
    # A real caller accepts altered identities: this is part of #112's validator
    # boundary, not a new repair. Synthetic fixtures are labeled as such.
    before = load_segment_tree(
        ROOT / "tests/fixtures/mutations/management_fee_bump/before_segments.json"
    )
    after = load_segment_tree(
        ROOT / "tests/fixtures/mutations/management_fee_bump/after_segments.json"
    )
    before["source_sha256"] = "forged-unbound-source"
    before["segments"][0]["segment_id"] = "unbound-segment"
    observations.append(
        observe(
            "forged source and segment identity in actual production caller",
            lambda: detect_change_classes(before, after),
        )
    )
    fixture = ROOT / "tests/fixtures/fact_key_map/tracked_variables.json"
    manifest = export_fact_key_map(fixture, destination / "fact-map")
    controls["fact_map_manifest"] = json.loads(manifest.read_text())
    controls["fact_map"] = json.loads((manifest.parent / "fact_key_map.json").read_text())
    controls["vocabulary_keys"] = load_legal_clauses()
    (destination / "observations.json").write_text(
        json.dumps({"controls": controls, "observations": observations}, indent=2, default=str)
        + "\n"
    )
    print(json.dumps(observations, indent=2, default=str))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
