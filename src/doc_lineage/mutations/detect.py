"""Detect labeled change classes between synthetic mutation segment trees."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from doc_lineage.blackline import align_sections, build_section_tree
from doc_lineage.ingest import Segment

GATE_PROVISION_SECTION_RE = re.compile(r"^\d+\.\s+MANAGEMENT FEE\b")


def load_segment_tree(path: Path) -> dict[str, Any]:
    """Load a segment-tree JSON fixture."""
    return json.loads(path.read_text(encoding="utf-8"))


def _segments_from_payload(payload: dict[str, Any]) -> tuple[Segment, ...]:
    return tuple(Segment(**entry) for entry in payload["segments"])


def detect_change_classes(
    before: dict[str, Any],
    after: dict[str, Any],
) -> tuple[str, ...]:
    """Return labeled change classes present between two segment trees."""
    before_doc = build_section_tree(
        _segments_from_payload(before),
        source_sha256=before["source_sha256"],
    )
    after_doc = build_section_tree(
        _segments_from_payload(after),
        source_sha256=after["source_sha256"],
    )
    pairs = align_sections(before_doc, after_doc)
    classes: list[str] = []
    for pair in pairs:
        if pair.left is None or pair.right is None:
            continue
        if pair.left.text == pair.right.text:
            continue
        if GATE_PROVISION_SECTION_RE.match(pair.left.text):
            classes.append("gate_provision_change")
    return tuple(classes)
