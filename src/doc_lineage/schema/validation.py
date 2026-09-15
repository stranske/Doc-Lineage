"""JSON Schema loading and record validation."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator


def _reject_non_finite_numbers(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}" if path else key
            _reject_non_finite_numbers(value, child)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _reject_non_finite_numbers(item, f"{path}[{index}]")
    elif isinstance(payload, float) and not math.isfinite(payload):
        raise ValueError(f"{path or 'value'} must be finite")


def _schema_resource(name: str) -> Path:
    filename = f"{name}.schema.json"
    try:
        resource = files("doc_lineage.schema").joinpath("schemas", filename)
        return Path(str(resource))
    except ModuleNotFoundError:
        checkout_root = Path(__file__).resolve().parents[3]
        return checkout_root / "schemas" / filename


@lru_cache(maxsize=32)
def load_schema(name: str) -> dict[str, Any]:
    path = _schema_resource(name)
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate_record(schema_name: str, payload: dict[str, Any]) -> None:
    _reject_non_finite_numbers(payload)
    schema = load_schema(schema_name)
    Draft202012Validator(schema).validate(payload)
