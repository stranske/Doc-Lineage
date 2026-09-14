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
    try:
        resource = files("doc_lineage._vocab").joinpath("legal-clauses.json")
    except ModuleNotFoundError as exc:
        module = Path(__file__).resolve()
        root = module.parents[2]
        if (
            exc.name != "doc_lineage._vocab"
            or module.parent != root / "src" / "doc_lineage"
            or not (root / "pyproject.toml").is_file()
        ):
            raise
        resource = root / "vocab" / "legal-clauses.json"
    text = resource.read_text(encoding="utf-8")
    return cast(dict[str, Any], json.loads(text))
