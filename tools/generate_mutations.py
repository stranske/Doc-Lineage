#!/usr/bin/env python3
"""Generate paired before/after synthetic LPA segment trees for mutation CI gates."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from doc_lineage.mutations.catalog import MUTATION_SPECS, MutationSpec

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "blackline" / "lpa_before_segments.json"
OUTPUT_ROOT = REPO_ROOT / "tests" / "fixtures" / "mutations"
SECTION_HEADER_RE = re.compile(r"^(\d+)\.\s+")


def _apply_spec(payload: dict, spec: MutationSpec) -> dict:
    mutated = copy.deepcopy(payload)
    for segment in mutated["segments"]:
        header = SECTION_HEADER_RE.match(segment["text"])
        if header is None or header.group(1) != spec.section_id:
            continue
        if spec.find not in segment["text"]:
            raise ValueError(
                f"mutation {spec.mutation_id}: find text {spec.find!r} missing in section "
                f"{spec.section_id}"
            )
        segment["text"] = segment["text"].replace(spec.find, spec.replace, 1)
        segment["char_count"] = len(segment["text"])
        segment["word_count"] = len(segment["text"].split())
        break
    else:
        raise ValueError(f"mutation {spec.mutation_id}: section {spec.section_id} not found")
    return mutated


def generate(output_root: Path = OUTPUT_ROOT) -> dict:
    """Write mutation pair fixtures and return the manifest payload."""
    output_root = output_root.resolve()
    output_root.relative_to(REPO_ROOT)  # Validate before creating any files.
    base = json.loads(BASE_FIXTURE.read_text(encoding="utf-8"))
    manifest_entries: list[dict[str, str]] = []
    for spec in MUTATION_SPECS:
        pair_dir = output_root / spec.mutation_id
        pair_dir.mkdir(parents=True, exist_ok=True)
        before_path = pair_dir / "before_segments.json"
        after_path = pair_dir / "after_segments.json"
        after_payload = _apply_spec(base, spec)
        # These fixtures model synthetic sources, identified by an explicit seed.
        seed = f"synthetic-mutation/v1:{base['source_sha256']}:{spec!r}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        after_payload["source_sha256"] = digest
        for segment in after_payload["segments"]:
            segment["segment_id"] = digest[:16] + segment["segment_id"][16:]
        before_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
        after_path.write_text(json.dumps(after_payload, indent=2) + "\n", encoding="utf-8")
        manifest_entries.append(
            {
                "mutation_id": spec.mutation_id,
                "change_class": spec.change_class,
                "before": str(before_path.relative_to(REPO_ROOT)),
                "after": str(after_path.relative_to(REPO_ROOT)),
            }
        )
    manifest = {"schema_version": "mutation-manifest/v1", "mutations": manifest_entries}
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_ROOT,
        help="Directory for generated mutation fixtures",
    )
    args = parser.parse_args()
    manifest = generate(args.output)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
