"""Regression: ingest module import must not load schema validation eagerly."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from doc_lineage.ingest import MANIFEST_SCHEMA_NAME, build_manifest


def test_ingest_import_does_not_load_validator_module() -> None:
    """Importing doc_lineage.ingest must not pull in schema.validation."""
    import doc_lineage as doc_lineage_pkg

    saved_modules: dict[str, object] = {}
    saved_ingest_attr = getattr(doc_lineage_pkg, "ingest", None)
    for name in list(sys.modules):
        if (
            name == "doc_lineage.ingest"
            or name.startswith("doc_lineage.ingest.")
            or name == "doc_lineage.schema.validation"
            or name.startswith("doc_lineage.schema.")
        ):
            saved_modules[name] = sys.modules.pop(name)

    try:
        import doc_lineage.ingest  # noqa: F401

        assert "doc_lineage.schema.validation" not in sys.modules
    finally:
        for name in list(sys.modules):
            if (
                (
                    name == "doc_lineage.ingest"
                    or name.startswith("doc_lineage.ingest.")
                    or name == "doc_lineage.schema.validation"
                    or name.startswith("doc_lineage.schema.")
                )
                and name not in saved_modules
            ):
                del sys.modules[name]
        sys.modules.update(saved_modules)
        if saved_ingest_attr is not None:
            doc_lineage_pkg.ingest = saved_ingest_attr
        elif hasattr(doc_lineage_pkg, "ingest"):
            delattr(doc_lineage_pkg, "ingest")


def test_build_manifest_invokes_validator_before_return(tmp_path: Path) -> None:
    """build_manifest must validate via lazy import before returning."""
    source = tmp_path / "sample.pdf"
    source.write_bytes(b"%PDF-1.4 minimal")

    with patch("doc_lineage.schema.validation.validate_contract_record") as validate_mock:
        manifest = build_manifest(
            run_id="test-run",
            source_path=source,
            source_sha256="abc123",
            artifacts=[
                {
                    "artifact_id": "abc123-segments",
                    "name": "segments.json",
                    "kind": "data",
                    "path": "segments.json",
                    "sha256": "def456",
                    "bytes": 10,
                    "media_type": "application/json",
                }
            ],
        )

    validate_mock.assert_called_once_with(MANIFEST_SCHEMA_NAME, manifest)
    assert manifest["schema_version"] == "artifact-manifest/v1"
