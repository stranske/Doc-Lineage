"""JSON Schema loading and record validation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _schemas_root() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas"


@lru_cache(maxsize=32)
def load_schema(name: str) -> dict[str, Any]:
    path = _schemas_root() / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_record(schema_name: str, payload: dict[str, Any]) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema).validate(payload)
