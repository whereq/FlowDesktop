"""Collect the latest quote for every symbol in the universe.

Source: Yahoo Finance (no API key required).

Quotes are appended to the ``quotes`` table — one row per symbol per
collection run — so the app can show a price history even for symbols that
are no longer trading. The unique constraint on ``(stock_id, timestamp)`` makes
re-running a collection idempotent within the same timestamp.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("flowdesk-collector.collectors.quotes")

#: Yahoo tolerates batched quote requests; keep the chunk modest to stay polite.
BATCH_SIZE = 50


async def collect_quotes(session, symbols: list[str] | None = None) -> dict:
    """Fetch and store the latest quote for each symbol.

    Returns ``{"fetched": n, "stored": m, "failed": k}``.
    """
    from sqlalchemy import select

    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_collector.providers.yahoo import YahooFinanceProvider
    from flowdesk_core.models.stock import Stock

    if symbols is None:
        symbols = await active_symbols(session)
    if not symbols:
        return {"fetched": 0, "stored": 0, "failed": 0}

    stock_rows = (
        (await session.execute(select(Stock.id, Stock.symbol).where(Stock.symbol.in_(symbols))))
        .tuples()
        .all()
    )
    stock_ids = {sym: sid for sid, sym in stock_rows}

    provider = YahooFinanceProvider()
    stored = failed = 0

    for i in range(0, len(symbols), BATCH_SIZE):
        chunk = symbols[i : i + BATCH_SIZE]
        try:
            quotes = await provider.get_quotes_batch(chunk)
        except Exception:
            logger.warning("Quote batch failed (%d symbols)", len(chunk), exc_info=True)
            failed += len(chunk)
            continue

        for q in quotes:
            sid = stock_ids.get(q.symbol)
            if sid is None:
                continue
            session.add(_quote_row(sid, q))
            stored += 1
        await session.commit()
        # Be polite between batches — Yahoo rate-limits aggressive callers.
        await asyncio.sleep(0.5)

    logger.info("Quotes collected: %d stored, %d failed", stored, failed)
    return {"fetched": len(symbols), "stored": stored, "failed": failed}


def _quote_row(stock_id: int, q):
    """Map a provider quote onto a ``Quote`` ORM row."""
    from flowdesk_core.models.quote import Quote

    return Quote(
        stock_id=stock_id,
        price=q.price,
        open_price=q.open_price,
        high=q.high,
        low=q.low,
        close=q.close,
        volume=q.volume,
        change=q.change,
        change_percent=q.change_percent,
        provider=q.provider or "yahoo",
        timestamp=q.timestamp,
    )
