"""Small pure helpers shared by routers."""

from __future__ import annotations

from typing import Any

from .models import Column, QueryResult

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def rows_as_dicts(result: QueryResult) -> list[dict[str, Any]]:
    names = [c.name for c in result.columns]
    return [dict(zip(names, row, strict=False)) for row in result.rows]


def month_key(value: Any) -> str | None:
    """Return a 'YYYY-MM' key from a date/timestamp string."""
    if not value:
        return None
    s = str(value)
    # Handles 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS...', or 'YYYY-MM'.
    return s[:7] if len(s) >= 7 else None


def month_label(value: Any) -> str | None:
    """Return a human label like 'June 2024' from a date/timestamp string."""
    key = month_key(value)
    if not key:
        return None
    try:
        year, month = key.split("-")
        return f"{_MONTHS[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return key


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 2)


def columns(names: list[str]) -> list[Column]:
    return [Column(name=n, type="string") for n in names]
