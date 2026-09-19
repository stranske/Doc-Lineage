"""Project tracked-variable identities into a manifest-backed Mosaic join map."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from doc_lineage.identity import sha256_bytes

FACT_KEY_MAP_FILENAME = "fact_key_map.json"
_ENTITY_REF = re.compile(r"[a-z0-9_]+:[a-z0-9][a-z0-9_.:-]*")


def build_fact_key_map(records: Iterable[Mapping[str, object]]) -> dict[str, dict[str, str]]:
    """Map variable IDs to exact ontology/entity joins, retaining an optional period.

    This validates the identity projection, not the upstream evidence/provenance
    payload. Incomplete identities and conflicting duplicate IDs fail closed.
    """
    result: dict[str, dict[str, str]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("each tracked variable must be an object")
        if record.get("schema_version") != "tracked-variable/v1":
            raise ValueError("schema_version must be tracked-variable/v1")
        fields: dict[str, str] = {}
        for name in ("variable_id", "ontology_key", "entity_ref"):
            value = record.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
            fields[name] = value
        if not _ENTITY_REF.fullmatch(fields["entity_ref"]):
            raise ValueError("entity_ref must be a canonical entity ID")
        variable_id = fields.pop("variable_id")
        if "period" in record:
            period = record["period"]
            if not isinstance(period, str) or not period.strip():
                raise ValueError("period must be a non-empty string when present")
            fields["period"] = period
        if variable_id in result and result[variable_id] != fields:
            raise ValueError(f"conflicting identity for variable_id {variable_id!r}")
        result[variable_id] = fields
    if not result:
        raise ValueError("at least one tracked variable is required")
    return dict(sorted(result.items()))


def export_fact_key_map(source: Path, output_dir: Path) -> Path:
    """Read a JSON array and publish its map and manifest in a fresh run directory.

    Existing output artifacts are never overwritten, including ingest manifests.
    The caller retains ownership of upstream tracked-variable extraction.
    """
    from doc_lineage.schema.validation import validate_contract_record

    raw = source.read_bytes()
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError("tracked-variable input must be a JSON array")
    mapping = build_fact_key_map(records)
    payload = (json.dumps(mapping, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = sha256_bytes(payload)
    manifest = {
        "schema_version": "artifact-manifest/v1",
        "run_id": f"fact-key-map-{digest[:16]}",
        "tool": "doc-lineage-fact-key-map",
        "source": {"filename": source.name, "sha256": sha256_bytes(raw), "bytes": len(raw)},
        "artifacts": [
            {
                "artifact_id": f"fact-key-map-{digest}",
                "name": "artifact:fact_key_map.json",
                "kind": "data",
                "path": FACT_KEY_MAP_FILENAME,
                "sha256": digest,
                "bytes": len(payload),
                "media_type": "application/json",
            }
        ],
    }
    validate_contract_record("artifact-manifest-v1", manifest)
    # Creating the directory exclusively also prevents clobbering an ingest run
    # or following a pre-existing output-file symlink outside the run directory.
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / FACT_KEY_MAP_FILENAME).write_bytes(payload)
    manifest_path = output_dir / "artifact-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path
