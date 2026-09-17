#!/usr/bin/env python3
"""Validate the public fixture corpus manifest against artifact-manifest/v1."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "tests" / "fixtures" / "public_corpus" / "manifest.json"
SCHEMA_PATH = REPO_ROOT / "docs" / "contracts" / "schemas" / "artifact-manifest-v1.schema.json"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def validate_manifest(manifest: dict, *, repo_root: Path = REPO_ROOT) -> list[str]:
    errors: list[str] = []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        try:
            from jsonschema import Draft202012Validator

            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            errors.extend(
                f"{error.json_path}: {error.message}"
                for error in Draft202012Validator(schema).iter_errors(manifest)
            )
        except ImportError:
            errors.append("/artifacts: artifacts must be a list")
        return errors

    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"/artifacts/{index}: artifact must be an object")
            continue
        content_sha256 = artifact.get("content_sha256")
        sha256 = artifact.get("sha256")
        if isinstance(content_sha256, str) and content_sha256 != sha256:
            errors.append(
                f"/artifacts/{index}: content_sha256 must match sha256 when both are present"
            )
        for field in ("sha256", "content_sha256"):
            value = artifact.get(field)
            if isinstance(value, str) and not SHA256_RE.fullmatch(value):
                errors.append(f"/artifacts/{index}/{field}: invalid sha256 length or charset")
        rel_path = artifact.get("path")
        if isinstance(rel_path, str):
            local_path = repo_root / rel_path
            if local_path.is_file():
                import hashlib

                digest = hashlib.sha256(local_path.read_bytes()).hexdigest()
                if isinstance(sha256, str) and digest != sha256:
                    errors.append(
                        f"/artifacts/{index}/sha256: does not match checked-in file {rel_path}"
                    )

    try:
        from jsonschema import Draft202012Validator

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        errors.extend(
            f"{error.json_path}: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(manifest)
        )
    except ImportError:
        pass
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to public_corpus/manifest.json",
    )
    args = parser.parse_args(argv)
    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    errors = validate_manifest(manifest)
    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        return 1
    print(f"OK: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
