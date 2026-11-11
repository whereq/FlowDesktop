"""Lazy on-view population for the StockDetail market-data panels.

The scheduled sync jobs cover the whole universe (bounded per run). When a
user opens a symbol that has no data yet, these helpers fetch it live — once —
from the whereq.cloud Data API and cache it in the same tables, so the panels
fill in on first view and stay cheap thereafter.

Guardrails: only symbols in our `stocks` universe; a per-symbol asyncio lock to
avoid concurrent-duplicate fetches (stampede); a timeout on each call; and
every failure degrades to a no-op (the panel just self-hides). Off if
settings.lazy_market_data_enabled is False.

SEC filing *narrative* is not fetched here: the Data API exposes filing
metadata by CIK, not the 10-K/10-Q text, and does not map a ticker to a CIK.
See ``docs/data-sources.md``.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.config import get_settings
from flowdesk_core.models.stock import Stock

logger = logging.getLogger(__name__)
settings = get_settings()

_locks: dict[str, asyncio.Lock] = {}


def _lock(key: str) -> asyncio.Lock:
    return _locks.setdefault(key, asyncio.Lock())


async def _in_universe(db: AsyncSession, symbol: str) -> bool:
    return bool(await db.scalar(select(Stock.id).where(Stock.symbol == symbol).limit(1)))


async def ensure_short_interest(db: AsyncSession, symbol: str) -> None:
    """Fetch and cache short interest for a symbol, once."""
    if not settings.lazy_market_data_enabled:
        return
    from flowdesk_collector.collectors.mapping import short_interest_values
    from flowdesk_core.models.short_interest import ShortInterest
    from flowdesk_core.whereq_cloud import WhereqCloudClient

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
            async with WhereqCloudClient() as client:
                rows = await asyncio.wait_for(client.short_interest(sym), timeout=15)
        except Exception:
            return
        stored = 0
        for si in rows or []:
            values = short_interest_values(si)
            if values is None:
                continue
            await db.execute(
                pg_insert(ShortInterest)
                .values(symbol=sym[:32], **values)
                .on_conflict_do_nothing(constraint="uq_short_interest_symbol_date")
            )
            stored += 1
        if stored:
            await db.commit()
            logger.info("lazy: fetched %d short-interest rows for %s", stored, sym)


async def ensure_insider(db: AsyncSession, symbol: str) -> None:
    """Fetch and cache insider Form 4 transactions for a symbol, once."""
    if not settings.lazy_market_data_enabled:
        return
    from flowdesk_collector.collectors.mapping import insider_values
    from flowdesk_core.models.insider_transaction import InsiderTransaction
    from flowdesk_core.whereq_cloud import WhereqCloudClient

    sym = (symbol or "").strip().upper()
    if not sym:
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
            async with WhereqCloudClient() as client:
                txns = await asyncio.wait_for(
                    client.insider_transactions(sym, days=365), timeout=20
                )
        except Exception:
            return
        stored = 0
        for t in txns or []:
            values = insider_values(t)
            if values is None:
                continue
            await db.execute(
                pg_insert(InsiderTransaction)
                .values(symbol=sym[:20], cik=None, **values)
                .on_conflict_do_nothing(constraint="uq_insider_txn")
            )
            stored += 1
        if stored:
            await db.commit()
            logger.info("lazy: fetched %d insider txns for %s", stored, sym)


async def ensure_filings(db: AsyncSession, symbol: str) -> None:
    """No-op: there is no filing-narrative source in the Data API.

    The table, the tool and the UI panel are all still in place — populate
    ``company_filings`` yourself (or point FlowDesktop at your own EDGAR
    source) to fill them. See ``docs/data-sources.md``.
    """
    return
