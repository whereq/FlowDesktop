"""Per-symbol market-data panels for the StockDetail page.

Thin public reads over the tables NOVA already ingests (insider Form 4, short
interest, congressional trades, SEC filings). Reuses the ToolRegistry handlers so
the UI and NOVA return the exact same shapes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services import lazy_market_data as lazy
from api.services.tool_registry import ToolRegistry
from flowdesk_core.database import get_db

router = APIRouter(prefix="/stocks", tags=["market-data"])

_tools = ToolRegistry()


@router.get("/{symbol}/insider")
async def insider_activity(
    symbol: str, days: int = 180, db: AsyncSession = Depends(get_db)
) -> dict:
    """Recent SEC Form 4 insider transactions + net buy/sell summary."""
    await lazy.ensure_insider(db, symbol)
    return await _tools._get_insider_activity(db, symbol, days=days)


@router.get("/{symbol}/short-interest")
async def short_interest(symbol: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Latest short-interest snapshot + month-over-month change."""
    await lazy.ensure_short_interest(db, symbol)
    return await _tools._get_short_interest(db, symbol)


@router.get("/{symbol}/congress")
async def congress_trades(symbol: str, limit: int = 15, db: AsyncSession = Depends(get_db)) -> dict:
    """Recent congressional (STOCK Act) disclosures for the symbol."""
    return await _tools._get_congress_trades(db, symbol, limit=limit)


@router.get("/{symbol}/filings")
async def filings(symbol: str, limit: int = 6, db: AsyncSession = Depends(get_db)) -> dict:
    """Recent SEC 10-K/10-Q filings (metadata + link) for the symbol."""
    from flowdesk_core.models.company_filing import CompanyFiling

    await lazy.ensure_filings(db, symbol)
    sym = (symbol or "").strip().upper()
    limit = max(1, min(int(limit or 6), 20))
    rows = (
        (
            await db.execute(
                select(CompanyFiling)
                .where(CompanyFiling.symbol == sym)
                .order_by(CompanyFiling.filing_date.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "symbol": sym,
        "count": len(rows),
        "filings": [
            {
                "form": r.form,
                "filing_date": r.filing_date.isoformat() if r.filing_date else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
                "title": r.title,
                "url": r.url,
            }
            for r in rows
        ],
    }
