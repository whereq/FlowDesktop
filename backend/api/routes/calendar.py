"""Earnings & dividend calendar API.

Reads the market_events table (populated by the collector's FMP bulk sync).
Auth required, consistent with the other market-data routes.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import get_current_user
from flowdesk_core.database import get_db
from flowdesk_core.models.market_event import VALID_EVENT_KINDS, MarketEvent
from flowdesk_core.models.stock import Stock

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _serialize(ev: MarketEvent, name: str | None) -> dict:
    return {
        "symbol": ev.symbol,
        "name": name,
        "kind": ev.kind,
        "event_date": ev.event_date.isoformat(),
        "time_of_day": ev.time_of_day,
        "eps_estimate": float(ev.eps_estimate) if ev.eps_estimate is not None else None,
        "eps_actual": float(ev.eps_actual) if ev.eps_actual is not None else None,
        "revenue_estimate": float(ev.revenue_estimate) if ev.revenue_estimate is not None else None,
        "revenue_actual": float(ev.revenue_actual) if ev.revenue_actual is not None else None,
        "fiscal_period": ev.fiscal_period,
        "amount": float(ev.amount) if ev.amount is not None else None,
        "currency": ev.currency,
        "pay_date": ev.pay_date.isoformat() if ev.pay_date else None,
        "record_date": ev.record_date.isoformat() if ev.record_date else None,
        "frequency": ev.frequency,
    }


@router.get("/events")
async def list_events(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    kind: str | None = Query(None),
    symbol: str | None = Query(None),
    symbols: str | None = Query(None, description="Comma-separated tickers (e.g. watchlist)"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Calendar events in a date range (default: today → +14 days)."""
    today = date.today()
    frm = from_date or today
    to = to_date or (today + timedelta(days=14))

    q = (
        select(MarketEvent, Stock.name)
        .join(Stock, Stock.symbol == MarketEvent.symbol, isouter=True)
        .where(MarketEvent.event_date >= frm, MarketEvent.event_date <= to)
        .order_by(MarketEvent.event_date.asc(), MarketEvent.symbol.asc())
        .limit(limit)
    )
    if kind in VALID_EVENT_KINDS:
        q = q.where(MarketEvent.kind == kind)
    if symbol:
        q = q.where(MarketEvent.symbol == symbol.strip().upper())
    if symbols:
        wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()][:100]
        if wanted:
            q = q.where(MarketEvent.symbol.in_(wanted))

    rows = (await db.execute(q)).all()
    return {
        "from": frm.isoformat(),
        "to": to.isoformat(),
        "count": len(rows),
        "events": [_serialize(ev, name) for ev, name in rows],
    }


@router.get("/upcoming/{symbol}")
async def upcoming_for_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
) -> dict:
    """Next earnings and next dividend for one symbol (for the stock page badge)."""
    sym = symbol.strip().upper()
    today = date.today()

    async def _next(kind: str) -> MarketEvent | None:
        return await db.scalar(
            select(MarketEvent)
            .where(
                MarketEvent.symbol == sym,
                MarketEvent.kind == kind,
                MarketEvent.event_date >= today,
            )
            .order_by(MarketEvent.event_date.asc())
            .limit(1)
        )

    earnings = await _next("earnings")
    dividend = await _next("dividend")
    return {
        "symbol": sym,
        "next_earnings": _serialize(earnings, None) if earnings else None,
        "next_dividend": _serialize(dividend, None) if dividend else None,
    }
