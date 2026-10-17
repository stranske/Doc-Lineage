"""A schema-valid object or a recomputed hash cannot hide a broken evidence link."""

import json
from pathlib import Path

import pytest

from doc_lineage.extract.variables import publish_variables
from doc_lineage.identity import sha256_bytes
from doc_lineage.ingest import ingest_document

SOURCE = Path(__file__).parents[1] / "fixtures" / "synthetic_lpa.pdf"


def _rewrite(run, path, change, *, rehash=True):
    target = run / path
    value = json.loads(target.read_text())
    change(value)
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    target.write_bytes(raw)
    if rehash:
        manifest_path = run / "artifact-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest["artifacts"]:
            if entry["path"] == path:
                entry.update(sha256=sha256_bytes(raw), bytes=len(raw))
        manifest_path.write_text(json.dumps(manifest))


@pytest.mark.parametrize(
    "failure",
    [
        "stale_hash",
        "source_digest",
        "segment_digest",
        "segment_id",
        "segment_page",
        "segment_count",
        "segment_type",
        "evidence_quote",
        "evidence_page",
        "evidence_source",
        "evidence_method",
        "evidence_schema",
        "duplicate_path",
        "duplicate_id",
        "missing_reference",
        "unlisted_evidence",
        "extra_artifact",
        "path_escape",
        "symlink",
        "duplicate_json_key",
        "missing_segments",
        "bad_source",
        "bad_coverage",
        "bad_backend",
        "artifact_identity",
        "coverage_counts",
        "no_segments",
    ],
)
def test_tracked_variable_rejects_corrupted_provenance_before_publication(tmp_path, failure):
    ingested = ingest_document(
        SOURCE, output_dir=tmp_path / "ingest", allow_docling=False, ocr_enabled=False
    )
    run = ingested.output_dir
    evidence_path = next((run / "evidence").glob("*.json")).relative_to(run).as_posix()
    if failure == "stale_hash":
        _rewrite(run, "segments.json", lambda p: p.update(backend="changed"), rehash=False)
    elif failure == "source_digest":
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p["source"].update(sha256="0" * 64),
            rehash=False,
        )
    elif failure.startswith("segment_"):
        field, value = {
            "segment_digest": ("source_sha256", "0" * 64),
            "segment_id": ("segment_id", "unrelated"),
            "segment_page": ("page", 0),
            "segment_count": ("char_count", 0),
            "segment_type": ("page", "one"),
        }[failure]
        _rewrite(
            run,
            "segments.json",
            lambda p: (p if field == "source_sha256" else p["segments"][0]).update({field: value}),
        )
    elif failure.startswith("evidence_"):
        field, value = {
            "evidence_quote": ("excerpt", "invented fee"),
            "evidence_page": ("locator", {"page": 20, "order": 1}),
            "evidence_source": ("source_id", "0" * 64),
            "evidence_method": ("method", "manual"),
            "evidence_schema": ("excerpt", 12),
        }[failure]
        _rewrite(run, evidence_path, lambda p: p.update({field: value}))
    elif failure == "duplicate_path":
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p["artifacts"].append(p["artifacts"][0]),
            rehash=False,
        )
    elif failure == "duplicate_id":
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p["artifacts"][1].update(artifact_id=p["artifacts"][0]["artifact_id"]),
            rehash=False,
        )
    elif failure == "missing_reference":
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p.update(artifacts=p["artifacts"][:1]),
            rehash=False,
        )
    elif failure == "unlisted_evidence":
        (run / "evidence" / "extra.json").write_text("{}")
    elif failure == "extra_artifact":
        (run / "extra.json").write_bytes(b"{}")
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p["artifacts"].append(
                {
                    "artifact_id": "extra",
                    "path": "extra.json",
                    "name": "extra",
                    "sha256": sha256_bytes(b"{}"),
                    "bytes": 2,
                }
            ),
            rehash=False,
        )
    elif failure == "path_escape":
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p["artifacts"][0].update(path="../escape.json"),
            rehash=False,
        )
    elif failure == "symlink":
        original = (run / evidence_path).read_bytes()
        outside = tmp_path / "outside.json"
        outside.write_bytes(original)
        (run / evidence_path).unlink()
        (run / evidence_path).symlink_to(outside)
    elif failure == "duplicate_json_key":
        path = run / "artifact-manifest.json"
        path.write_text(
            path.read_text().replace(
                '"tool": "doc-lineage-ingest"', '"tool": "wrong", "tool": "doc-lineage-ingest"'
            )
        )
    elif failure == "missing_segments":
        (run / "segments.json").unlink()
    elif failure == "bad_source":
        _rewrite(run, "artifact-manifest.json", lambda p: p.update(source=[]), rehash=False)
    elif failure == "bad_coverage":
        _rewrite(run, "segments.json", lambda p: p.update(coverage=[]))
    elif failure == "bad_backend":
        _rewrite(run, "segments.json", lambda p: p.update(backend="unknown"))
    elif failure == "artifact_identity":
        _rewrite(
            run,
            "artifact-manifest.json",
            lambda p: p["artifacts"][0].update(artifact_id="foreign-segments"),
            rehash=False,
        )
    elif failure == "coverage_counts":
        _rewrite(run, "segments.json", lambda p: p["coverage"].update(pages_total=0))
    elif failure == "no_segments":
        _rewrite(run, "segments.json", lambda p: p.update(segments=[]))
    output = tmp_path / "extract"
    with pytest.raises((ValueError, OSError)):
        publish_variables(run, SOURCE, output, entity_ref="fund:alpha_iv")
    assert not output.exists()


def test_tracked_variable_partial_coverage_is_unresolved(tmp_path):
    ingested = ingest_document(
        SOURCE, output_dir=tmp_path / "ingest", allow_docling=False, ocr_enabled=False
    )
    _rewrite(
        ingested.output_dir,
        "segments.json",
        lambda p: p.update(
            coverage={
                "status": "partial",
                "pages_total": 3,
                "pages_with_text_layer": 2,
                "pages_recognized": 0,
                "pages_unreadable": 1,
            },
            unreadable_pages=[3],
        ),
    )
    output = tmp_path / "extract"
    publish_variables(ingested.output_dir, SOURCE, output, entity_ref="fund:alpha_iv")
    assert json.loads((output / "tracked-variables.json").read_text()) == []
    assert (
        json.loads((output / "unresolved.json").read_text())[0]["reason"]
        == "incomplete_ingest_coverage"
    )
