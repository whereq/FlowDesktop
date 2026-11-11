"""Sync the ``stocks`` table from the whereq.cloud Data API catalog.

The catalog is the source of truth for the instrument universe. This collector
walks it exchange by exchange — the catalog's exchange list carries each
exchange's market and currency, which the per-symbol listing does not — and
upserts every instrument into ``stocks``.

Symbols are never hard-deleted. An instrument that stops being covered is
marked ``is_active = False`` so its quotes and history stay intact.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("flowdesk-collector.collectors.universe")

#: How many catalog rows to request per page.
PAGE_SIZE = 1000


async def sync_universe(session, max_per_exchange: int | None = None) -> dict:
    """Upsert the whole instrument universe from the Data API catalog.

    Returns ``{"inserted": n, "updated": m, "total": t, "deactivated": d}``.
    """
    from sqlalchemy import select

    from flowdesk_core.models.stock import Stock
    from flowdesk_core.whereq_cloud import WhereqCloudClient

    async with WhereqCloudClient() as client:
        exchanges = await client.exchanges()

        existing = {s.symbol: s for s in (await session.execute(select(Stock))).scalars().all()}
        seen: set[str] = set()
        inserted = updated = 0

        for ex in exchanges:
            code = (ex.get("code") or "").strip()
            market = (ex.get("market") or "US").strip() or "US"
            currency = (ex.get("currency") or "USD").strip() or "USD"
            if not code:
                continue

            offset = 0
            total = None
            while total is None or offset < total:
                total, rows = await client.symbols_page(
                    exchange=code,
                    limit=PAGE_SIZE,
                    offset=offset,
                )
                if not rows:
                    break
                for row in rows:
                    symbol = (row.get("symbol") or "").strip().upper()
                    name = (row.get("name") or "").strip()
                    if not symbol or not name:
                        continue
                    seen.add(symbol)
                    stock = existing.get(symbol)
                    if stock is None:
                        session.add(
                            Stock(
                                symbol=symbol,
                                name=name,
                                name_cn=(row.get("name_cn") or None),
                                exchange=code,
                                sector=(row.get("sector") or None),
                                market=market,
                                currency=currency,
                                market_cap=row.get("market_cap"),
                                is_active=True,
                            )
                        )
                        inserted += 1
                    else:
                        stock.name = name
                        if row.get("name_cn"):
                            stock.name_cn = row["name_cn"]
                        stock.exchange = code
                        if row.get("sector"):
                            stock.sector = row["sector"]
                        stock.market = market
                        stock.currency = currency
                        if row.get("market_cap"):
                            stock.market_cap = row["market_cap"]
                        updated += 1
                offset += len(rows)
                if max_per_exchange and offset >= max_per_exchange:
                    break

        # Anything the catalog no longer lists is soft-deleted, never removed.
        deactivated = 0
        for symbol, stock in existing.items():
            if symbol not in seen and stock.is_active:
                stock.is_active = False
                deactivated += 1

        await session.commit()

    logger.info(
        "Universe synced: %d inserted, %d updated, %d deactivated, %d total",
        inserted,
        updated,
        deactivated,
        len(seen),
    )
    return {
        "inserted": inserted,
        "updated": updated,
        "deactivated": deactivated,
        "total": len(seen),
    }


async def active_symbols(session, limit: int | None = None) -> list[str]:
    """Return the active symbols, optionally limited (highest priority first)."""
    from sqlalchemy import select

    from flowdesk_core.models.stock import Stock

    stmt = (
        select(Stock.symbol)
        .where(Stock.is_active == True)  # noqa: E712
        .order_by(Stock.priority_tier.asc(), Stock.symbol.asc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars().all())
