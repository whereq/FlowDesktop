"""Sync the latest quote for every symbol in the universe.

Source: the whereq.cloud Data API (``/v1/equities/quotes``), fetched with the
operator's API key.

Quotes are appended to the ``quotes`` table — one row per symbol per
collection run — so the app can show a price history even for symbols that
are no longer trading. The unique constraint on ``(stock_id, timestamp)`` makes
re-running a collection idempotent within the same timestamp.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("flowdesk-collector.collectors.quotes")

#: The Data API accepts at most 50 symbols per batch request.
BATCH_SIZE = 50


async def collect_quotes(session, symbols: list[str] | None = None) -> dict:
    """Fetch and store the latest quote for each symbol.

    Returns ``{"fetched": n, "stored": m, "failed": k}``.
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from flowdesk_collector.collectors.mapping import quote_values
    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_core.models.quote import Quote
    from flowdesk_core.models.stock import Stock
    from flowdesk_core.whereq_cloud import WhereqCloudClient

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
    if not stock_ids:
        return {"fetched": 0, "stored": 0, "failed": 0}

    stored = failed = 0

    async with WhereqCloudClient() as client:
        for i in range(0, len(symbols), BATCH_SIZE):
            chunk = symbols[i : i + BATCH_SIZE]
            try:
                rows = await client.quotes(chunk)
            except Exception:
                logger.warning("Quote batch failed (%d symbols)", len(chunk), exc_info=True)
                failed += len(chunk)
                continue

            for q in rows:
                sid = stock_ids.get((q.get("symbol") or "").strip().upper())
                if sid is None:
                    continue
                values = quote_values(q)
                if values is None:
                    continue
                # The API keeps the same timestamp until a new quote lands, so
                # a re-run would collide on (stock_id, timestamp). Upsert with
                # a conflict guard instead of letting the batch abort.
                await session.execute(
                    pg_insert(Quote)
                    .values(stock_id=sid, **values)
                    .on_conflict_do_nothing(constraint="uq_quotes_stock_timestamp")
                )
                stored += 1
            await session.commit()

    logger.info("Quotes synced: %d stored, %d failed", stored, failed)
    return {"fetched": len(symbols), "stored": stored, "failed": failed}
