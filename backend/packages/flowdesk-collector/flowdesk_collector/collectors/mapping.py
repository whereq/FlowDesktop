"""Map whereq.cloud Data API payloads onto FlowDesktop ORM rows.

Pure functions only — no database, no network — so every mapping is unit
testable on its own. The API and the ORM agree on most field names; the
exceptions are handled here:

* the API sends decimal numbers as strings (``"325.7500"``) — they become
  :class:`~decimal.Decimal` columns;
* the API sends timestamps as naive ISO strings;
* insider transactions carry a stable platform row ``id`` but no CIK, so the
  id doubles as the ``line_index`` that keeps ``(accession, line_index)``
  unique across re-syncs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

#: The provider label stored on synced rows.
PROVIDER = "whereq_cloud"


def to_decimal(value) -> Decimal | None:
    """Coerce an API number (or numeric string) into a ``Decimal``."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def to_int(value) -> int | None:
    """Coerce an API number (or numeric string) into an ``int``."""
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def to_float(value) -> float | None:
    """Coerce an API number (or numeric string) into a ``float``."""
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def to_date(value) -> date | None:
    """Coerce an API date string into a ``date``."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def to_datetime(value) -> datetime | None:
    """Coerce an API timestamp into a naive ``datetime``.

    The API emits naive local timestamps without a zone suffix. A timestamp
    that *does* carry one is converted to UTC and stripped, so the column
    (which is timezone-naive) always holds UTC.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def quote_values(q: dict) -> dict | None:
    """Map an API quote row onto ``Quote`` column values.

    Returns ``None`` when the row carries no price — a quote without a price
    says nothing.
    """
    price = to_decimal(q.get("price"))
    if price is None:
        return None
    return {
        "price": price,
        "open_price": to_decimal(q.get("open_price")),
        "high": to_decimal(q.get("high")),
        "low": to_decimal(q.get("low")),
        "close": to_decimal(q.get("close")),
        "volume": to_int(q.get("volume")),
        "change": to_decimal(q.get("change")),
        "change_percent": to_decimal(q.get("change_percent")),
        "provider": (q.get("provider") or PROVIDER)[:50],
        "timestamp": to_datetime(q.get("timestamp")) or datetime.now(UTC).replace(tzinfo=None),
    }


def history_values(h: dict) -> dict | None:
    """Map an API history bar onto ``HistoricalPrice`` column values."""
    day = to_date(h.get("date"))
    if day is None:
        return None
    return {
        "date": day,
        "open_price": to_decimal(h.get("open_price")),
        "high": to_decimal(h.get("high")),
        "low": to_decimal(h.get("low")),
        "close": to_decimal(h.get("close")),
        "adj_close": to_decimal(h.get("adj_close")),
        "volume": to_int(h.get("volume")),
        "provider": (h.get("provider") or PROVIDER)[:50],
        "adjustment": (h.get("adjustment") or "unknown")[:32],
    }


def short_interest_values(si: dict) -> dict | None:
    """Map an API short-interest row onto ``ShortInterest`` column values.

    Returns ``None`` when the row carries no share count — ``short_interest``
    is NOT NULL and a row without it says nothing.
    """
    shares = to_int(si.get("short_interest"))
    settlement = to_date(si.get("settlement_date"))
    if shares is None or settlement is None:
        return None
    return {
        "settlement_date": settlement,
        "short_interest": shares,
        "prior_short_interest": to_int(si.get("prior_short_interest")),
        "avg_daily_volume": to_int(si.get("avg_daily_volume")),
        "days_to_cover": to_float(si.get("days_to_cover")),
        "short_pct_of_float": to_float(si.get("short_pct_of_float")),
        "short_pct_of_outstanding": to_float(si.get("short_pct_of_outstanding")),
        "change_pct": to_float(si.get("change_pct")),
        "source": (si.get("source") or "whereq.cloud")[:32],
    }


def insider_values(t: dict) -> dict | None:
    """Map an API Form 4 transaction onto ``InsiderTransaction`` values.

    The API's stable platform row id becomes ``line_index`` so that the
    ``(accession, line_index)`` unique constraint keeps re-syncs idempotent.
    The API exposes no CIK, so ``cik`` stays ``None``.
    """
    accession = (t.get("accession") or "").strip()
    name = (t.get("insider_name") or "").strip()
    if not accession or not name:
        return None
    line_index = to_int(t.get("id"))
    return {
        "accession": accession[:30],
        "line_index": line_index if line_index is not None else 0,
        "filing_date": to_date(t.get("filing_date")),
        "transaction_date": to_date(t.get("transaction_date")),
        "insider_name": name[:150],
        "insider_title": (t.get("insider_title") or None),
        "is_director": False,
        "is_officer": False,
        "is_ten_pct": False,
        "transaction_code": (t.get("transaction_code") or None),
        "acquired_disposed": (t.get("acquired_disposed") or None),
        "shares": to_decimal(t.get("shares")),
        "price": to_decimal(t.get("price_per_share")),
        "value": to_decimal(t.get("total_value")),
        "shares_owned_after": to_decimal(t.get("shares_owned_after")),
    }
