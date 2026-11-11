"""Market hours detection for each supported exchange.

All comparisons are done in UTC. Holiday calendars are intentionally
not implemented here — a weekday + UTC-hour check is sufficient for the
scheduler's purpose (best-effort gate, not a strict trading calendar).

For production-grade holiday handling, integrate with a library such as
``exchange_calendars`` or ``pandas_market_calendars``.

Exchange UTC windows
---------------------
NYSE / NASDAQ / TSX
    Regular session: 9:30 AM – 4:00 PM ET
    EDT (UTC-4, ~Apr–Oct): 13:30 – 20:00 UTC
    EST (UTC-5, ~Nov–Mar): 14:30 – 21:00 UTC
    Conservative open window (covers both):  13:30 – 21:00 UTC

SSE (Shanghai) / SZSE (Shenzhen)
    Morning session: 9:30 – 11:30 CST  (UTC: 01:30 – 03:30)
    Lunch break:    11:30 – 13:00 CST  (UTC: 03:30 – 05:00)  ← skipped
    Afternoon session: 13:00 – 15:00 CST (UTC: 05:00 – 07:00)

HK (Hong Kong)
    Morning session:  9:30 – 12:00 HKT  (UTC: 01:30 – 04:00)
    Lunch break:     12:00 – 13:00 HKT  (UTC: 04:00 – 05:00)  ← skipped
    Afternoon session: 13:00 – 16:00 HKT (UTC: 05:00 – 08:00)

NSE (National Stock Exchange of India)
    Regular session: 9:15 – 15:30 IST  (UTC: 03:45 – 10:00)

LSE (London Stock Exchange)
    Regular session: 8:00 – 16:30 local
    GMT (UTC+0, ~Nov–Mar): 08:00 – 16:30 UTC
    BST (UTC+1, ~Apr–Oct): 07:00 – 15:30 UTC
    Conservative open window (covers both):  07:00 – 16:30 UTC

XETRA (Deutsche Börse, Frankfurt)
    Regular session: 9:00 – 17:30 local
    CET (UTC+1, ~Nov–Mar): 08:00 – 16:30 UTC
    CEST (UTC+2, ~Apr–Oct): 07:00 – 15:30 UTC
    Conservative open window (covers both):  07:00 – 16:30 UTC

B3 (Bolsa de Valores de São Paulo)
    Regular session: 10:00 – 17:00 BRT  (UTC: 13:00 – 20:00)
    BRT is UTC-3 with no DST (Brazil abolished it in 2019).

ASX (Australian Securities Exchange)
    Regular session: 10:00 – 16:00 local
    AEST (UTC+10, ~Apr–Oct): 00:00 – 06:00 UTC
    AEDT (UTC+11, ~Oct–Mar): 23:00 – 05:00 UTC (previous calendar day)
    Conservative open window (covers both):  23:00 – 06:00 UTC
    This window WRAPS MIDNIGHT — see the wrap handling in is_market_open().
"""

from datetime import UTC, datetime, time

# ---------------------------------------------------------------------------
# Market-hours table  (all times UTC, no DST adjustment needed for CN)
# ---------------------------------------------------------------------------

# (open_utc, close_utc) for the full outer trading window.
# Exchanges with a mid-session lunch break are listed in _LUNCH_BREAKS below.
_HOURS: dict[str, tuple[time, time]] = {
    # US/Canada — conservative window covers both EDT and EST
    "NYSE": (time(13, 30), time(21, 0)),
    "NASDAQ": (time(13, 30), time(21, 0)),
    "TSX": (time(13, 30), time(21, 0)),
    # China — CST is fixed (no DST); lunch break handled in _LUNCH_BREAKS
    "SSE": (time(1, 30), time(7, 0)),
    "SZSE": (time(1, 30), time(7, 0)),
    # Hong Kong — HKT is UTC+8, no DST; lunch break handled in _LUNCH_BREAKS
    "HK": (time(1, 30), time(8, 0)),
    # Japan (JPX/TSE) — JST is UTC+9, no DST
    #   Regular session: 9:00 am – 3:30 pm JST (00:00 – 06:30 UTC)
    "JPX": (time(0, 0), time(6, 30)),
    # Singapore (SGX) — SGT is UTC+8, no DST
    #   Regular session: 9:00 am – 5:00 pm SGT (01:00 – 09:00 UTC)
    "SGX": (time(1, 0), time(9, 0)),
    # Taiwan (TAI) — TST is UTC+8, no DST
    #   Regular session: 9:00 am – 1:30 pm TST (01:00 – 05:30 UTC)
    "TAI": (time(1, 0), time(5, 30)),
    # Korea (KSC) — KST is UTC+9, no DST
    #   Regular session: 9:00 am – 3:30 pm KST (00:00 – 06:30 UTC)
    "KSC": (time(0, 0), time(6, 30)),
    # India (NSE) — IST is UTC+5:30, no DST
    #   Regular session: 9:15 am – 3:30 pm IST (03:45 – 10:00 UTC)
    "NSE": (time(3, 45), time(10, 0)),
    # United Kingdom (LSE) — GMT (UTC+0) in winter, BST (UTC+1) in summer
    #   Regular session: 8:00 am – 4:30 pm local
    #   Conservative window covers both: 07:00 – 16:30 UTC
    "LSE": (time(7, 0), time(16, 30)),
    # Germany (XETRA / Frankfurt) — CET (UTC+1) winter, CEST (UTC+2) summer
    #   Regular session: 9:00 am – 5:30 pm local
    #   Conservative window covers both: 07:00 – 16:30 UTC
    "XETRA": (time(7, 0), time(16, 30)),
    # Brazil (B3 / BM&FBOVESPA) — BRT is UTC-3, no DST since 2019
    #   Regular session: 10:00 – 17:00 BRT (13:00 – 20:00 UTC)
    "B3": (time(13, 0), time(20, 0)),
    # Australia (ASX) — AEST (UTC+10) winter, AEDT (UTC+11) summer
    #   Regular session: 10:00 am – 4:00 pm local
    #   Conservative window covers both and WRAPS midnight: 23:00 – 06:00 UTC
    "ASX": (time(23, 0), time(6, 0)),
}

# Mid-session lunch breaks (UTC).  is_market_open() returns False during these
# windows even if the time falls within _HOURS.  Avoids hammering providers
# (AKShare, HKEX) when their data feed is inactive during the break.
_LUNCH_BREAKS: dict[str, tuple[time, time]] = {
    # SSE/SZSE: 11:30–13:00 CST = 03:30–05:00 UTC
    "SSE": (time(3, 30), time(5, 0)),
    "SZSE": (time(3, 30), time(5, 0)),
    # HKEX:  12:00–13:00 HKT = 04:00–05:00 UTC
    "HK": (time(4, 0), time(5, 0)),
}

# Map non-canonical exchange codes used internally (e.g. Yahoo Finance values)
# to the canonical codes above.
_NORMALIZE: dict[str, str] = {
    # NYSE variants from Yahoo Finance / Alpha Vantage
    "NYQ": "NYSE",
    "NMS": "NASDAQ",  # NASDAQ Global Select
    "NGM": "NASDAQ",  # NASDAQ Global Market
    "NGS": "NASDAQ",
    "NCM": "NASDAQ",  # NASDAQ Capital Market
    # Explicit pass-throughs
    "NYSE": "NYSE",
    "NASDAQ": "NASDAQ",
    "TSX": "TSX",
    # China
    "SSE": "SSE",
    "SZSE": "SZSE",
    # Hong Kong
    "HKG": "HK",
    "HK": "HK",
    # Japan
    "JPX": "JPX",
    "TSE": "JPX",
    "JPY": "JPX",  # currency code sometimes used as exchange hint
    # Singapore
    "SGX": "SGX",
    "SES": "SGX",
    # Taiwan
    "TAI": "TAI",
    "TW": "TAI",
    "Taiwan": "TAI",
    # Korea
    "KSC": "KSC",
    "KS": "KSC",
    "Korea": "KSC",
    # India — NSE and BSE share the same 09:15–15:30 IST session
    "NSE": "NSE",
    "NSI": "NSE",  # Yahoo Finance's code for the National Stock Exchange
    "BSE": "NSE",  # Bombay Stock Exchange — identical hours
    # United Kingdom
    "LSE": "LSE",
    "LON": "LSE",  # Yahoo Finance's code for the London Stock Exchange
    # Germany — XETRA (Frankfurt) is the cash-market reference
    "XETRA": "XETRA",
    "GER": "XETRA",  # Yahoo Finance's code for Germany
    "FRA": "XETRA",  # Yahoo Finance's code for Frankfurt
    # Brazil
    "B3": "B3",
    "SAO": "B3",  # Yahoo Finance's code for São Paulo
    "BVMF": "B3",  # B3's legacy identifier
    # Australia
    "ASX": "ASX",
    "AX": "ASX",  # Yahoo Finance's code for Australia
}


def normalize_exchange(exchange: str) -> str:
    """Return the canonical exchange code for market-hours lookup."""
    return _NORMALIZE.get(exchange.upper(), exchange.upper())


def is_market_open(exchange: str, now: datetime | None = None) -> bool:
    """Return True if *exchange* is in regular trading hours right now.

    Args:
        exchange: Exchange code (case-insensitive). Accepts both canonical
                  codes (NYSE, NASDAQ, TSX, SSE, SZSE) and Yahoo Finance
                  variants (NYQ, NMS, NGM, etc.).
        now:      Reference UTC datetime. Defaults to ``datetime.now(UTC)``.

    Returns:
        True  — weekday AND current UTC time is within the exchange's
                regular trading window.
        False — weekend, or outside trading hours, or unknown exchange.
    """
    if now is None:
        now = datetime.now(UTC)

    # Strip timezone for comparison (we assume *now* is already UTC)
    now_utc = now.replace(tzinfo=None) if now.tzinfo else now

    # Weekends: Saturday=5, Sunday=6
    if now_utc.weekday() >= 5:
        return False

    canonical = normalize_exchange(exchange)
    hours = _HOURS.get(canonical)
    if hours is None:
        return False

    current_time = now_utc.time()
    open_time, close_time = hours
    if open_time <= close_time:
        in_window = open_time <= current_time < close_time
    else:
        # The window wraps past midnight.  ASX is the case that needs it: its
        # 10:00–16:00 Sydney session is 00:00–06:00 UTC under AEST but
        # 23:00–05:00 UTC under AEDT, so the conservative window (23:00–06:00)
        # starts on one UTC day and ends on the next.
        in_window = current_time >= open_time or current_time < close_time
    if not in_window:
        return False

    # Exclude mid-session lunch breaks
    lunch = _LUNCH_BREAKS.get(canonical)
    return not (lunch and lunch[0] <= current_time < lunch[1])


def get_open_exchanges(now: datetime | None = None) -> list[str]:
    """Return canonical codes of all exchanges currently in trading hours."""
    return [ex for ex in _HOURS if is_market_open(ex, now)]


def any_market_open(
    exchanges: list[str] | None = None,
    now: datetime | None = None,
) -> bool:
    """Return True if at least one of *exchanges* is currently open.

    Args:
        exchanges: Subset of exchanges to check. If None, checks all known
                   exchanges.
        now:       Reference UTC datetime.
    """
    if exchanges is None:
        exchanges = list(_HOURS.keys())
    return any(is_market_open(ex, now) for ex in exchanges)


def is_us_market_open(now: datetime | None = None) -> bool:
    """Convenience: True if NYSE or NASDAQ is open (same hours)."""
    return is_market_open("NYSE", now)


def is_cn_market_open(now: datetime | None = None) -> bool:
    """Convenience: True if SSE or SZSE is open (same hours)."""
    return is_market_open("SSE", now)
