"""Lazy on-view population for the StockDetail market-data panels.

The weekly collector jobs only fetch *held* (watchlist/portfolio) symbols to bound
cost. When a user opens any other stock, these helpers fetch that symbol's data
live (once) and cache it in the same tables, so the panels fill in on first view
and stay cheap thereafter.

Guardrails: only symbols in our `stocks` universe; a per-symbol asyncio lock to
avoid concurrent-duplicate fetches (stampede); a timeout on each external call;
and every failure degrades to a no-op (the panel just self-hides). Off if
settings.lazy_market_data_enabled is False.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.config import get_settings
from flowdesk_core.models.stock import Stock

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level EDGAR provider so the CIK map is downloaded once per process.
from flowdesk_collector.providers.sec_edgar import SecEdgarProvider  # noqa: E402

_edgar = SecEdgarProvider()

_locks: dict[str, asyncio.Lock] = {}


def _lock(key: str) -> asyncio.Lock:
    return _locks.setdefault(key, asyncio.Lock())


async def _in_universe(db: AsyncSession, symbol: str) -> bool:
    return bool(await db.scalar(select(Stock.id).where(Stock.symbol == symbol).limit(1)))


def _short_interest_row(symbol: str, si: dict, today: date | None = None) -> dict | None:
    """Map a Yahoo-shaped provider dict to ShortInterest ORM column values.

    Pure function (no DB) so the mapping can be unit-tested.

    The provider (`collector.providers.short_interest`) returns Yahoo-shaped keys
    (`as_of_date`, `shares_short`, `short_ratio`, ...); the ShortInterest ORM
    columns are the FINRA-shaped live-table names (migration 155/212)
    (`settlement_date`, `short_interest`, `days_to_cover`, ...). This mirrors
    the platform collector's write path exactly.

    Returns None when the payload carries no share count — `short_interest` is
    NOT NULL and a row without it says nothing.
    """
    as_of = si.get("as_of_date") or today or date.today()
    shares_short = si.get("shares_short")
    if shares_short is None:
        return None
    prior = si.get("shares_short_prior")
    change_pct = None
    if prior:
        change_pct = round((int(shares_short) - int(prior)) / int(prior) * 100.0, 2)
    return {
        "symbol": symbol,
        "settlement_date": as_of,
        "short_interest": int(shares_short),
        "prior_short_interest": prior,
        "avg_daily_volume": si.get("avg_daily_volume"),
        "days_to_cover": si.get("short_ratio"),
        "short_pct_of_float": si.get("short_pct_float"),
        "short_pct_of_outstanding": si.get("short_pct_outstanding"),
        "change_pct": change_pct,
        "source": "Yahoo Finance",
    }


async def ensure_short_interest(db: AsyncSession, symbol: str) -> None:
    if not settings.lazy_market_data_enabled:
        return
    from flowdesk_collector.providers.short_interest import fetch_short_interest
    from flowdesk_core.models.short_interest import ShortInterest

    sym = (symbol or "").strip().upper()
    if not sym:
        return
    if await db.scalar(select(ShortInterest.id).where(ShortInterest.symbol == sym).limit(1)):
        return
    if not await _in_universe(db, sym):
        return
    async with _lock(f"si:{sym}"):
        if await db.scalar(select(ShortInterest.id).where(ShortInterest.symbol == sym).limit(1)):
            return
        try:
            si = await asyncio.wait_for(fetch_short_interest(sym), timeout=15)
        except Exception:
            return
        if not si:
            return
        row = _short_interest_row(sym, si)
        if row is None:
            return
        await db.execute(
            pg_insert(ShortInterest)
            .values(**row)
            .on_conflict_do_nothing(constraint="uq_short_interest_symbol_date")
        )
        await db.commit()
        logger.info("lazy: fetched short interest for %s", sym)


async def ensure_insider(db: AsyncSession, symbol: str) -> None:
    if not settings.lazy_market_data_enabled:
        return
    from flowdesk_collector.providers.sec_insider import fetch_recent_form4
    from flowdesk_core.models.insider_transaction import InsiderTransaction

    sym = (symbol or "").strip().upper()
    if not sym or "." in sym:  # SEC = US only (bare tickers)
        return
    if await db.scalar(
        select(InsiderTransaction.id).where(InsiderTransaction.symbol == sym).limit(1)
    ):
        return
    if not await _in_universe(db, sym):
        return
    async with _lock(f"f4:{sym}"):
        if await db.scalar(
            select(InsiderTransaction.id).where(InsiderTransaction.symbol == sym).limit(1)
        ):
            return
        try:
            cik = await _edgar.get_cik(sym)
            if not cik:
                return
            txns = await asyncio.wait_for(fetch_recent_form4(cik, max_filings=6), timeout=20)
        except Exception:
            return
        stored = 0
        for t in txns:
            res = await db.execute(
                pg_insert(InsiderTransaction)
                .values(
                    symbol=sym,
                    cik=cik,
                    accession=t["accession"],
                    line_index=t["line_index"],
                    filing_date=t.get("filing_date"),
                    transaction_date=t.get("transaction_date"),
                    insider_name=t["insider_name"],
                    insider_title=t.get("insider_title"),
                    is_director=t.get("is_director", False),
                    is_officer=t.get("is_officer", False),
                    is_ten_pct=t.get("is_ten_pct", False),
                    transaction_code=t.get("code"),
                    acquired_disposed=t.get("acquired_disposed"),
                    shares=t.get("shares"),
                    price=t.get("price"),
                    value=t.get("value"),
                    shares_owned_after=t.get("shares_after"),
                )
                .on_conflict_do_nothing(constraint="uq_insider_txn")
            )
            stored += res.rowcount or 0
        if stored:
            await db.commit()
            logger.info("lazy: fetched %d insider txns for %s", stored, sym)


async def ensure_filings(db: AsyncSession, symbol: str) -> None:
    if not settings.lazy_market_data_enabled:
        return
    from flowdesk_collector.providers.sec_filings import fetch_latest_filings
    from flowdesk_core.models.company_filing import CompanyFiling

    sym = (symbol or "").strip().upper()
    if not sym or "." in sym:  # US only
        return
    if await db.scalar(select(CompanyFiling.id).where(CompanyFiling.symbol == sym).limit(1)):
        return
    if not await _in_universe(db, sym):
        return
    async with _lock(f"filing:{sym}"):
        if await db.scalar(select(CompanyFiling.id).where(CompanyFiling.symbol == sym).limit(1)):
            return
        try:
            cik = await _edgar.get_cik(sym)
            if not cik:
                return
            filings = await asyncio.wait_for(fetch_latest_filings(cik, per_form=1), timeout=25)
        except Exception:
            return
        stored = 0
        for f in filings:
            if not f.get("content") or not f.get("filing_date"):
                continue
            res = await db.execute(
                pg_insert(CompanyFiling)
                .values(
                    symbol=sym,
                    cik=cik,
                    form=f["form"],
                    filing_date=f["filing_date"],
                    period_end=f.get("period_end"),
                    accession=f["accession"],
                    title=f.get("title"),
                    url=f.get("url"),
                    content=f["content"],
                )
                .on_conflict_do_nothing(constraint="uq_filing_accession")
            )
            stored += res.rowcount or 0
        if stored:
            await db.commit()
            logger.info("lazy: fetched %d filings for %s", stored, sym)
