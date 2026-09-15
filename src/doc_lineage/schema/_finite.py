"""Shared validation helpers for numeric ledger fields."""

from __future__ import annotations

import math
from typing import Any


def require_finite_number(value: Any, field_name: str) -> float:
    """Reject non-finite numbers at validation time."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def require_finite_int(value: Any, field_name: str) -> int:
    """Reject non-finite or non-integer numeric values at validation time."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite integer")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    if not number.is_integer():
        raise ValueError(f"{field_name} must be an integer")
    return int(number)
