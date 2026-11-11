"""Short-interest fetcher via Yahoo Finance (yfinance).

Yahoo's `Ticker(symbol).info` exposes short-interest fields for free (no key),
covering US + international. The parse helper is pure (dict → dict) so it's
unit-testable without the network. See docs/design/RFC_NOVA_ALTDATA_POSITIONING.md.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

logger = logging.getLogger(__name__)


def _to_date(ts) -> date | None:
    """Yahoo dateShortInterest is a unix-seconds timestamp."""
    try:
        return datetime.fromtimestamp(int(ts), tz=UTC).date() if ts else None
    except (ValueError, TypeError, OSError):
        return None


def _num(v):
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def parse_short_interest(info: dict | None) -> dict | None:
    """Extract short-interest fields from a yfinance `.info` dict.

    Returns None when the symbol carries no short-interest data at all. `as_of_date`
    may be None if Yahoo omits `dateShortInterest`; the caller coalesces to today.
    """
    if not info:
        return None
    shares_short = info.get("sharesShort")
    short_ratio = _num(info.get("shortRatio"))
    short_pct_float = _num(info.get("shortPercentOfFloat"))
    short_pct_out = _num(info.get("sharesPercentSharesOut"))
    if shares_short is None and short_ratio is None and short_pct_float is None:
        return None  # no short data for this name
    return {
        "as_of_date": _to_date(info.get("dateShortInterest")),
        "shares_short": int(shares_short) if shares_short is not None else None,
        "shares_short_prior": (
            int(info["sharesShortPriorMonth"])
            if info.get("sharesShortPriorMonth") is not None
            else None
        ),
        "short_ratio": short_ratio,
        "short_pct_float": short_pct_float,
        "short_pct_outstanding": short_pct_out,
        # Yahoo's 3-month average volume — the denominator the API's
        # "days to cover" is read against.
        "avg_daily_volume": (
            int(info["averageVolume"]) if info.get("averageVolume") is not None else None
        ),
    }


async def fetch_short_interest(symbol: str) -> dict | None:
    """Fetch + parse short interest for one symbol. None on no-data/failure."""
    try:
        import yfinance as yf

        info = await asyncio.to_thread(lambda: yf.Ticker(symbol).info)
        return parse_short_interest(info)
    except Exception as exc:
        logger.debug("fetch_short_interest failed for %s: %s", symbol, exc)
        return None
