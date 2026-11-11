"""Sync daily OHLCV history for the symbols that need it.

Source: the whereq.cloud Data API (``/v1/equities/{symbol}/history``),
fetched with the operator's API key.

History is backfilled incrementally: a symbol is skipped when it already has
rows inside the recency window. The unique constraint on
``(stock_id, date)`` keeps re-runs idempotent.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger("flowdesk-collector.collectors.history")

#: How far back to look on the first backfill for a symbol.
DEFAULT_LOOKBACK_DAYS = 365

#: A symbol with data this recent is considered up to date.
RECENCY_DAYS = 7

#: The Data API returns at most 2000 daily bars per request.
MAX_BARS = 2000


async def collect_history(
    session,
    symbols: list[str] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_symbols: int | None = None,
) -> dict:
    """Backfill daily history for symbols that are missing it.

    Returns ``{"fetched": n, "stored": m, "skipped": k}``.
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from flowdesk_collector.collectors.mapping import history_values
    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_core.models.historical import HistoricalPrice
    from flowdesk_core.models.stock import Stock
    from flowdesk_core.whereq_cloud import WhereqCloudClient

    if symbols is None:
        symbols = await active_symbols(session)
    if not symbols:
        return {"fetched": 0, "stored": 0, "skipped": 0}

    # Which symbols already have recent data?
    cutoff = date.today() - timedelta(days=RECENCY_DAYS)
    fresh = {
        sym
        for (sym,) in (
            await session.execute(
                select(Stock.symbol)
                .join(HistoricalPrice, HistoricalPrice.stock_id == Stock.id)
                .where(Stock.symbol.in_(symbols))
                .where(HistoricalPrice.date >= cutoff)
                .group_by(Stock.symbol)
            )
        ).all()
    }

    todo = [s for s in symbols if s not in fresh]
    if max_symbols:
        todo = todo[:max_symbols]
    if not todo:
        return {"fetched": 0, "stored": 0, "skipped": len(symbols)}

    stock_rows = (
        (await session.execute(select(Stock.id, Stock.symbol).where(Stock.symbol.in_(todo))))
        .tuples()
        .all()
    )
    stock_ids = {sym: sid for sid, sym in stock_rows}

    end = date.today()
    start = end - timedelta(days=lookback_days)
    stored = 0

    async with WhereqCloudClient() as client:
        for sym in todo:
            sid = stock_ids.get(sym)
            if sid is None:
                continue
            try:
                rows = await client.history(sym, start=start, end=end, limit=MAX_BARS)
            except Exception:
                logger.debug("History fetch failed for %s", sym, exc_info=True)
                continue
            if not rows:
                continue
            for h in rows:
                values = history_values(h)
                if values is None:
                    continue
                await session.execute(
                    pg_insert(HistoricalPrice)
                    .values(stock_id=sid, **values)
                    .on_conflict_do_nothing(constraint="uq_historical_stock_date")
                )
                stored += 1
            await session.commit()

    logger.info("History synced: %d rows for %d symbols", stored, len(todo))
    return {"fetched": len(todo), "stored": stored, "skipped": len(fresh)}
