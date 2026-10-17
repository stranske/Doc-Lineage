"""Bounded observations of documented downstream callers on final reviewed main.

This records actual outcomes; it does not assert continued failure after repairs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from doc_lineage.render import resolve_triple_link


def run(claims: Path) -> None:
    records = json.loads((claims / "tracked-variables.json").read_text())
    record = records[0]
    result = {
        "producer": "cli.main -> publish_variables -> ingest._extract_verified",
        "consumer": "doc_lineage.render.resolve_triple_link",
        "contract": "docs/triple-link-resolver.md; tracked-variable/v1 provenance",
        "input_claims_sha256": hashlib.sha256(
            (claims / "tracked-variables.json").read_bytes()
        ).hexdigest(),
        "input_evidence_sha256": hashlib.sha256(
            (claims / record["evidence_ref"]).read_bytes()
        ).hexdigest(),
        "input_variable_id": record["variable_id"],
        "input_evidence_id": record["evidence"]["evidence_id"],
        "provenance": record["provenance"],
    }
    try:
        result["html"] = resolve_triple_link(record)
    except ValueError as exc:
        result["exception"] = type(exc).__name__
        result["message"] = str(exc)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
