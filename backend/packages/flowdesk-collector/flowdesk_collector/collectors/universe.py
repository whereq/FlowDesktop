"""Seed the ``stocks`` table from the bundled symbol universe.

The universe ships with the project as ``data/universe.csv`` — a plain list of
(symbol, name, exchange, sector, industry, market, currency). It is a
*starting point*, not gospel: edit it, or replace it with your own list, then
re-run this collector. Symbols are never hard-deleted; a symbol that stops
being collected is marked ``is_active = False`` so its history is preserved.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger("flowdesk-collector.collectors.universe")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNIVERSE_CSV = DATA_DIR / "universe.csv"

#: Column order in ``universe.csv``.
_COLUMNS = (
    "symbol",
    "name",
    "name_cn",
    "exchange",
    "sector",
    "industry",
    "market_cap",
    "market",
    "currency",
    "priority_tier",
    "is_active",
)


def load_universe(path: Path | None = None) -> list[dict]:
    """Read the bundled universe CSV into a list of dicts."""
    csv_path = path or UNIVERSE_CSV
    if not csv_path.exists():
        logger.warning("Universe CSV not found at %s", csv_path)
        return []
    rows: list[dict] = []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            rows.append(
                {
                    "symbol": (raw.get("symbol") or "").strip().upper(),
                    "name": (raw.get("name") or "").strip(),
                    "name_cn": (raw.get("name_cn") or "").strip() or None,
                    "exchange": (raw.get("exchange") or "").strip() or None,
                    "sector": (raw.get("sector") or "").strip() or None,
                    "industry": (raw.get("industry") or "").strip() or None,
                    "market_cap": _int_or_none(raw.get("market_cap")),
                    "market": (raw.get("market") or "US").strip() or "US",
                    "currency": (raw.get("currency") or "USD").strip() or "USD",
                    "priority_tier": _int_or_none(raw.get("priority_tier")) or 2,
                    "is_active": _bool(raw.get("is_active")),
                }
            )
    return [r for r in rows if r["symbol"] and r["name"]]


def _int_or_none(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _bool(value) -> bool:
    return str(value).strip().lower() in ("1", "t", "true", "yes", "y")


async def seed_universe(session, path: Path | None = None) -> dict:
    """Insert or update every symbol in the universe.

    Returns a summary dict with ``inserted`` / ``updated`` / ``total``.
    """
    from sqlalchemy import select

    from flowdesk_core.models.stock import Stock

    rows = load_universe(path)
    if not rows:
        return {"inserted": 0, "updated": 0, "total": 0}

    existing = {s.symbol: s for s in (await session.execute(select(Stock))).scalars().all()}

    inserted = updated = 0
    for row in rows:
        stock = existing.get(row["symbol"])
        if stock is None:
            session.add(Stock(**row))
            inserted += 1
            continue
        # Update the descriptive fields, but never resurrect an inactive symbol
        # automatically — deactivation is a deliberate decision.
        for key in ("name", "name_cn", "exchange", "sector", "industry", "market_cap"):
            if row.get(key) is not None:
                setattr(stock, key, row[key])
        updated += 1

    await session.commit()
    logger.info("Universe seeded: %d inserted, %d updated", inserted, updated)
    return {"inserted": inserted, "updated": updated, "total": len(rows)}


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
