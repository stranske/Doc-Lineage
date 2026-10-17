"""Validate persisted ingest provenance and publish bounded legal extractions.

This verifies consistency and hashes, not authenticity against a malicious party
who rewrites an entire ingest run. The original document is always required.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from doc_lineage.adapters import DOCLING_BACKEND, OFFLINE_BACKEND
from doc_lineage.adapters.docling_segmenter import MAX_INGEST_BYTES, read_bounded_bytes
from doc_lineage.identity import sha256_bytes
from doc_lineage.ingest import (
    MANIFEST_FILENAME,
    ORIGINAL_FILENAME,
    SEGMENTS_FILENAME,
    SEGMENTS_SCHEMA_VERSION,
    Segment,
    build_evidence_objects,
)
from doc_lineage.schema.validation import load_contract_schema, validate_contract_record


@dataclass(frozen=True)
class VerifiedIngest:
    digest: str
    source: bytes
    source_name: str
    segments: tuple[Segment, ...]
    evidence: tuple[dict[str, Any], ...]
    files: dict[str, bytes]
    manifest: dict[str, Any]
    complete: bool


def dump_json(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _object(raw: bytes) -> dict[str, Any]:
    obj = json.loads(raw, object_pairs_hook=_unique)
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    return obj


def validate(schema: str, payload: dict[str, Any]) -> None:
    try:
        if schema == "tracked-variable-v1":
            # Resolve the shared contract's evidence $ref locally, never over
            # the network (the generic validator only handles standalone schemas).
            contracts = [load_contract_schema(name) for name in (schema, "evidence-object-v1")]
            registry: Registry[Any] = Registry().with_resources(
                (s["$id"], Resource.from_contents(s)) for s in contracts
            )
            Draft202012Validator(contracts[0], registry=registry).validate(payload)
        else:
            validate_contract_record(schema, payload)
    except ValidationError as exc:
        raise ValueError(f"invalid {schema}: {exc.message}") from exc


def _read_local(root: Path, relative: str) -> bytes:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise ValueError("ingest artifact path must be relative and normalized")
    target = root / path
    if not target.resolve().is_relative_to(root) or any(
        part.is_symlink() for part in (target, *target.parents) if part != root.parent
    ):
        raise ValueError("ingest artifact must not traverse symlinks or escape its run")
    return read_bounded_bytes(target, MAX_INGEST_BYTES)


def load_ingest(ingest_dir: Path, source: Path) -> VerifiedIngest:
    """Read and validate every listed artifact and every segment/evidence link."""
    root = ingest_dir.expanduser().resolve()
    manifest_raw = _read_local(root, MANIFEST_FILENAME)
    manifest = _object(manifest_raw)
    validate("artifact-manifest-v1", manifest)
    if manifest.get("tool") != "doc-lineage-ingest":
        raise ValueError("input must be a doc-lineage-ingest run")
    raw = read_bounded_bytes(source, MAX_INGEST_BYTES)
    digest = sha256_bytes(raw)
    source_info = manifest.get("source", {})
    if not isinstance(source_info, dict):
        raise ValueError("invalid source provenance")
    name = source_info.get("filename", "")
    if (
        source_info.get("sha256") != digest
        or source_info.get("bytes") != len(raw)
        or not isinstance(name, str)
        or not name
        or Path(name).name != name
        or name in {".", ".."}
    ):
        raise ValueError("original source digest, byte count or filename mismatch")
    original_path = ORIGINAL_FILENAME.format(sha256=digest)
    artifacts: dict[str, bytes] = {}
    artifact_ids: set[str] = set()
    for entry in manifest["artifacts"]:
        path = entry["path"]
        if path in artifacts or entry["artifact_id"] in artifact_ids:
            raise ValueError("duplicate ingest artifact path or identity")
        data = _read_local(root, path)
        if sha256_bytes(data) != entry["sha256"] or len(data) != entry.get("bytes"):
            raise ValueError(f"ingest artifact hash or byte count mismatch: {path}")
        artifacts[path] = data
        artifact_ids.add(entry["artifact_id"])
        if path == original_path:
            expected_id, expected_kind = f"{digest}-original", "data"
            if data != raw:
                raise ValueError("retained original snapshot differs from source")
        elif path == SEGMENTS_FILENAME:
            expected_id, expected_kind = f"{digest[:16]}-segments", "data"
        else:
            expected_id, expected_kind = f"{Path(path).stem}-evidence", "evidence"
        if entry["artifact_id"] != expected_id or entry.get("kind") != expected_kind:
            raise ValueError("ingest artifact identity or kind mismatch")
    if SEGMENTS_FILENAME not in artifacts:
        raise ValueError("ingest manifest must reference segments.json")
    payload = _object(artifacts[SEGMENTS_FILENAME])
    if (
        payload.get("schema_version") != SEGMENTS_SCHEMA_VERSION
        or payload.get("source_sha256") != digest
        or payload.get("backend") not in {OFFLINE_BACKEND, DOCLING_BACKEND}
    ):
        raise ValueError("segments provenance or format mismatch")
    try:
        segments = tuple(Segment(**s) for s in payload["segments"])
    except (TypeError, KeyError) as exc:
        raise ValueError("invalid ingest segment structure") from exc
    if not segments:
        raise ValueError("ingest must contain segments")
    for order, segment in enumerate(segments, 1):
        if (
            type(segment.page) is not int
            or segment.page < 1
            or type(segment.order) is not int
            or segment.order != order
            or segment.segment_id != f"{digest[:16]}-p{segment.page:04d}-s{order:04d}"
            or not isinstance(segment.text, str)
            or not segment.text.strip()
            or segment.char_count != len(segment.text)
            or segment.word_count != len(segment.text.split())
            or type(segment.char_count) is not int
            or type(segment.word_count) is not int
            or segment.method not in {"text", "parser", "ocr"}
        ):
            raise ValueError("segment identity, text counts or location mismatch")
    expected = build_evidence_objects(segments, source_id=digest, backend=payload["backend"])
    expected_paths = {SEGMENTS_FILENAME}
    # Earlier main ingests predate retained snapshots; validate one when present.
    if original_path in artifacts:
        expected_paths.add(original_path)
    for evidence in expected:
        path = f"evidence/{evidence['evidence_id']}.json"
        expected_paths.add(path)
        if path not in artifacts:
            raise ValueError("missing segment evidence reference")
        persisted = _object(artifacts[path])
        validate("evidence-object-v1", persisted)
        if persisted != evidence:
            raise ValueError("segment/evidence provenance mismatch")
    if set(artifacts) != expected_paths:
        raise ValueError("unexpected or unreferenced ingest evidence artifact")
    if {
        p.relative_to(root).as_posix() for p in (root / "evidence").glob("*.json")
    } != expected_paths - {SEGMENTS_FILENAME, original_path}:
        raise ValueError("unlisted evidence object in ingest run")
    artifacts["input-manifest.json"] = manifest_raw
    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("missing ingest coverage")
    counts = [
        coverage.get(key)
        for key in ("pages_total", "pages_with_text_layer", "pages_recognized", "pages_unreadable")
    ]
    if any(type(count) is not int or count < 0 for count in counts):
        raise ValueError("invalid ingest coverage counts")
    integer_counts = cast(list[int], counts)
    unreadable = payload.get("unreadable_pages")
    if (
        coverage["pages_total"] < max(s.page for s in segments)
        or coverage["pages_total"] != sum(integer_counts[1:])
        or not isinstance(unreadable, list)
        or any(
            type(page) is not int or not 1 <= page <= coverage["pages_total"] for page in unreadable
        )
        or len(set(unreadable)) != len(unreadable)
        or len(unreadable) != coverage["pages_unreadable"]
        or set(unreadable) & {s.page for s in segments}
        or coverage.get("status") != ("partial" if unreadable else "complete")
        or len({s.page for s in segments}) + len(unreadable) != coverage["pages_total"]
    ):
        raise ValueError("ingest coverage provenance mismatch")
    complete = coverage.get("status") == "complete" and payload.get("unreadable_pages") == []
    return VerifiedIngest(digest, raw, name, segments, expected, artifacts, manifest, complete)


def validate_entity(entity_ref: str) -> None:
    if not re.fullmatch(
        r"(?:manager|fund|pension|provider|person|strategy):[a-z0-9][a-z0-9_.:-]*", entity_ref
    ):
        raise ValueError("entity_ref must be a canonical entity ID with a supported entity type")


def publish_variables(ingest_dir: Path, source: Path, output_dir: Path, *, entity_ref: str) -> Path:
    """Publish validated records, original evidence and source bytes into a new run."""
    from doc_lineage.ingest import _extract_verified

    verified = load_ingest(ingest_dir, source)
    result = _extract_verified(verified, entity_ref=entity_ref)
    files = dict(verified.files)
    files["tracked-variables.json"] = dump_json(result["records"])
    files["unresolved.json"] = dump_json(result["unresolved"])
    files[f"source/{verified.source_name}"] = verified.source
    manifest = {
        "schema_version": "artifact-manifest/v1",
        "run_id": result["run_id"],
        "tool": "doc-lineage-extract-variables",
        "source": verified.manifest["source"],
        "input_manifest_sha256": sha256_bytes(files["input-manifest.json"]),
        "artifacts": [
            {
                "artifact_id": f"extraction-{sha256_bytes(path.encode())[:16]}",
                "name": Path(path).name,
                "kind": (
                    "tracked_variables"
                    if path == "tracked-variables.json"
                    else "evidence" if path.startswith("evidence/") else "data"
                ),
                "path": path,
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "media_type": (
                    "application/json" if path.endswith(".json") else "application/octet-stream"
                ),
            }
            for path, data in sorted(files.items())
        ],
    }
    validate("artifact-manifest-v1", manifest)
    output_dir.mkdir(parents=True, exist_ok=False)
    for path, data in files.items():
        target = output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_bytes(dump_json(manifest))
    return manifest_path
