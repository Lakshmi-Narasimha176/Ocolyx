"""Validation helper utilities."""

from typing import Any


def is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0
