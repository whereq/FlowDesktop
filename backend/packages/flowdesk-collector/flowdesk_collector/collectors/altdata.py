"""Sync alternative data: short interest and insider Form 4 transactions.

Source: the whereq.cloud Data API, fetched with the operator's API key.

* ``/v1/alt/short-interest/{symbol}`` — settlement-date snapshots
* ``/v1/alt/insider/{symbol}``          — Form 4 ownership transactions

**What is not here.** The whereq.cloud Data API exposes SEC filings by CIK and
returns filing-level metadata — form, dates, accession, document URL — but not
the 10-K/10-Q *narrative* that FlowDesktop's filing-grounding index embeds, and
it does not map a ticker to a CIK. FlowDesktop therefore does not populate
``company_filings`` out of the box; see ``docs/data-sources.md``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("flowdesk-collector.collectors.altdata")


async def collect_insider_transactions(
    session,
    symbols: list[str] | None = None,
    days: int = 365,
    max_symbols: int | None = None,
) -> dict:
    """Fetch recent insider Form 4 transactions for each symbol.

    Returns ``{"fetched": n, "stored": m}``.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from flowdesk_collector.collectors.mapping import insider_values
    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_core.models.insider_transaction import InsiderTransaction
    from flowdesk_core.whereq_cloud import WhereqCloudClient

    if symbols is None:
        symbols = await active_symbols(session)
    if max_symbols:
        symbols = symbols[:max_symbols]
    if not symbols:
        return {"fetched": 0, "stored": 0}

    stored = 0

    async with WhereqCloudClient() as client:
        for sym in symbols:
            try:
                txns = await client.insider_transactions(sym, days=days)
            except Exception:
                logger.debug("Form 4 fetch failed for %s", sym, exc_info=True)
                continue
            for t in txns:
                values = insider_values(t)
                if values is None:
                    continue
                await session.execute(
                    pg_insert(InsiderTransaction)
                    .values(symbol=sym[:20], cik=None, **values)
                    .on_conflict_do_nothing(constraint="uq_insider_txn")
                )
                stored += 1
            if stored:
                await session.commit()

    logger.info("Insider transactions synced: %d stored", stored)
    return {"fetched": len(symbols), "stored": stored}


async def collect_short_interest(
    session,
    symbols: list[str] | None = None,
    max_symbols: int | None = None,
) -> dict:
    """Fetch the latest short-interest snapshot for each symbol.

    Returns ``{"fetched": n, "stored": m}``.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from flowdesk_collector.collectors.mapping import short_interest_values
    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_core.models.short_interest import ShortInterest
    from flowdesk_core.whereq_cloud import WhereqCloudClient

    if symbols is None:
        symbols = await active_symbols(session)
    if max_symbols:
        symbols = symbols[:max_symbols]
    if not symbols:
        return {"fetched": 0, "stored": 0}

    stored = 0

    async with WhereqCloudClient() as client:
        for sym in symbols:
            try:
                rows = await client.short_interest(sym)
            except Exception:
                logger.debug("Short interest fetch failed for %s", sym, exc_info=True)
                continue
            for si in rows:
                values = short_interest_values(si)
                if values is None:
                    continue
                await session.execute(
                    pg_insert(ShortInterest)
                    .values(symbol=sym[:32], **values)
                    .on_conflict_do_nothing(constraint="uq_short_interest_symbol_date")
                )
                stored += 1
            if stored:
                await session.commit()

    logger.info("Short interest synced: %d stored", stored)
    return {"fetched": len(symbols), "stored": stored}
