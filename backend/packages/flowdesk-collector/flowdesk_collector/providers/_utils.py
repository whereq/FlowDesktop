"""Shared utility functions for data provider implementations."""

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation


def safe_decimal(value) -> Decimal | None:
    """Convert a pandas/numpy value to Decimal, returning None on failure."""
    try:
        import pandas as pd

        if pd.isna(value):
            return None
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def safe_int(value) -> int | None:
    """Convert a pandas/numpy value to int, returning None on failure."""
    try:
        import pandas as pd

        if pd.isna(value):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_get(info, key):
    """Safely get a value from a yfinance info/fast_info object."""
    try:
        return info.get(key)
    except (AttributeError, TypeError):
        return None


def safe_decimal_from_info(info, key) -> Decimal | None:
    """Extract a Decimal from a yfinance info/fast_info object by key."""
    try:
        val = info.get(key)
        if val is None:
            return None
        return Decimal(str(val))
    except (AttributeError, TypeError, ValueError, InvalidOperation):
        return None


def safe_int_from_info(info, key) -> int | None:
    """Extract an int from a yfinance info/fast_info object by key."""
    try:
        val = info.get(key)
        if val is None:
            return None
        return int(float(val))
    except (AttributeError, TypeError, ValueError):
        return None


def utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def parse_date(value) -> date | None:
    """Parse a date from various formats, returning None on failure."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
