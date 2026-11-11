"""Congressional stock-trade fetcher (STOCK Act disclosures).

Pulls the community senate/house-stock-watcher public datasets. Third-party,
best-effort — coverage and latency vary, and the schema can drift, so parsing is
defensive and the normalize helpers are pure (unit-testable). See
docs/design/RFC_NOVA_ALTDATA_POSITIONING.md.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date

import aiohttp

from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)


def _pdate(s) -> date | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime

            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _txn_type(raw: str | None) -> str | None:
    t = (raw or "").strip().lower()
    if t.startswith("purchase") or t == "buy":
        return "buy"
    if t.startswith("sale") or t.startswith("sell"):
        return "sell"
    if t.startswith("exchange"):
        return "exchange"
    return None


def normalize_congress_row(row: dict, chamber: str) -> dict | None:
    """Normalize one raw dataset row → a CongressTrade-shaped dict, or None if it
    has no usable ticker. `chamber` is 'senate' or 'house'."""
    ticker = (row.get("ticker") or "").strip().upper()
    if not ticker or ticker in ("--", "N/A", "NONE"):
        return None
    politician = (
        row.get("senator") if chamber == "senate" else row.get("representative")
    ) or "Unknown"
    txn_date = _pdate(row.get("transaction_date"))
    amount = (row.get("amount") or "").strip() or None
    txn_type = _txn_type(row.get("type"))
    key = f"{chamber}|{politician}|{ticker}|{txn_date}|{txn_type}|{amount}"
    return {
        "dedup_hash": hashlib.sha1(key.encode("utf-8")).hexdigest(),
        "symbol": ticker,
        "chamber": chamber,
        "politician": politician[:150],
        "party": (row.get("party") or None),
        "transaction_date": txn_date,
        "disclosure_date": _pdate(row.get("disclosure_date")),
        "txn_type": txn_type,
        "amount_range": amount[:60] if amount else None,
        "source": f"{chamber}-stock-watcher",
    }


# --- FMP congress source (API key) -------------------------------------------
# Preferred over the (now-403) community S3 buckets when an FMP key is present.
# Uses the "stable" latest-disclosure feeds (the v4 endpoints are deprecated and
# the per-symbol stable endpoints are a higher tier). Both feeds share one shape.
FMP_SENATE_RSS = "https://financialmodelingprep.com/stable/senate-latest?page={page}&apikey={key}"
FMP_HOUSE_RSS = "https://financialmodelingprep.com/stable/house-latest?page={page}&apikey={key}"


def _fmp_politician(row: dict, chamber: str) -> str:
    name = f"{row.get('firstName', '')} {row.get('lastName', '')}".strip()
    return name or row.get("office") or row.get("representative") or "Unknown"


def normalize_fmp_row(row: dict, chamber: str) -> dict | None:
    """Normalize one FMP congress RSS row → CongressTrade-shaped dict, or None."""
    ticker = (row.get("symbol") or row.get("ticker") or "").strip().upper()
    if not ticker or ticker in ("--", "N/A", "NONE"):
        return None
    politician = _fmp_politician(row, chamber)
    txn_date = _pdate(row.get("transactionDate"))
    amount = (row.get("amount") or "").strip() or None
    txn_type = _txn_type(row.get("type"))
    key = f"{chamber}|{politician}|{ticker}|{txn_date}|{txn_type}|{amount}"
    return {
        "dedup_hash": hashlib.sha1(key.encode("utf-8")).hexdigest(),
        "symbol": ticker,
        "chamber": chamber,
        "politician": politician[:150],
        "party": None,
        "transaction_date": txn_date,
        "disclosure_date": _pdate(row.get("disclosureDate") or row.get("dateRecieved")),
        "txn_type": txn_type,
        "amount_range": amount[:60] if amount else None,
        "source": f"fmp-{chamber}",
    }


async def fetch_congress_fmp(api_key: str, max_pages: int = 8) -> list[dict]:
    """Fetch + normalize congress trades from FMP RSS feeds (needs a free key)."""
    out: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for tmpl, chamber in ((FMP_SENATE_RSS, "senate"), (FMP_HOUSE_RSS, "house")):
            for page in range(max_pages):
                rows = await _fetch_json(session, tmpl.format(page=page, key=api_key))
                if not isinstance(rows, list) or not rows:
                    break
                for row in rows:
                    if isinstance(row, dict):
                        norm = normalize_fmp_row(row, chamber)
                        if norm:
                            out.append(norm)
    return out


async def _fetch_json(session, url: str) -> list:
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning("congress: %s → %s", url, resp.status)
                return []
            return await resp.json(content_type=None)
    except Exception as exc:
        logger.warning("congress: fetch failed %s: %s", url, exc)
        return []


async def fetch_congress_trades() -> list[dict]:
    """Fetch + normalize both chambers' disclosures. [] on failure (best-effort)."""
    out: list[dict] = []
    s = get_settings()
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for url, chamber in ((s.congress_senate_url, "senate"), (s.congress_house_url, "house")):
            if not url:
                continue
            rows = await _fetch_json(session, url)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                norm = normalize_congress_row(row, chamber)
                if norm:
                    out.append(norm)
    return out
