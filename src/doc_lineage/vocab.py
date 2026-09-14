"""Load the versioned vocabulary used for cross-manager clause joins."""

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast


def load_legal_clauses() -> dict[str, Any]:
    """Return a fresh vocabulary document, including metadata and the clauses map.

    The source checkout owns the JSON in ``vocab/``; wheels bundle that same
    directory as ``doc_lineage._vocab``. No working-directory dependency exists.
    """
    source = Path(__file__).resolve().parents[2] / "vocab" / "legal-clauses.json"
    if source.is_file():
        text = source.read_text(encoding="utf-8")
    else:
        text = (
            files("doc_lineage._vocab").joinpath("legal-clauses.json").read_text(encoding="utf-8")
        )
    return cast(dict[str, Any], json.loads(text))
