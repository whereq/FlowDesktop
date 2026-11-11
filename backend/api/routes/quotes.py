"""Quote-related API routes."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.quote import (
    HistoricalPriceResponse,
    IndexQuote,
    MarketOverview,
    MoverStock,
    QuoteWithSymbol,
)
from flowdesk_core.auth import get_current_user
from flowdesk_core.database import get_db
from flowdesk_core.models import HistoricalPrice, Quote, Stock

router = APIRouter(prefix="/quotes", tags=["quotes"], dependencies=[Depends(get_current_user)])


@router.get("/latest", response_model=list[QuoteWithSymbol])
async def get_latest_quotes(
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get latest quotes for stocks.

    Args:
        symbols: Optional comma-separated list of symbols to filter
        limit: Maximum number of quotes to return

    Returns:
        List of latest quotes with stock info
    """
    # Subquery for latest quote per stock
    latest_subq = (
        select(Quote.stock_id, func.max(Quote.timestamp).label("max_ts"))
        .group_by(Quote.stock_id)
        .subquery()
    )

    query = (
        select(Quote, Stock.symbol, Stock.name)
        .join(Stock, Quote.stock_id == Stock.id)
        .join(
            latest_subq,
            and_(Quote.stock_id == latest_subq.c.stock_id, Quote.timestamp == latest_subq.c.max_ts),
        )
    )

    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        query = query.where(Stock.symbol.in_(symbol_list))

    query = query.order_by(Stock.symbol).limit(limit)

    result = await db.execute(query)
    rows = result.fetchall()

    return [
        QuoteWithSymbol(
            id=row[0].id,
            stock_id=row[0].stock_id,
            price=row[0].price,
            open_price=row[0].open_price,
            high=row[0].high,
            low=row[0].low,
            close=row[0].close,
            volume=row[0].volume,
            change=row[0].change,
            change_percent=row[0].change_percent,
            provider=row[0].provider,
            timestamp=row[0].timestamp,
            created_at=row[0].created_at,
            symbol=row[1],
            name=row[2],
        )
        for row in rows
    ]


@router.get("/{symbol}/latest", response_model=QuoteWithSymbol)
async def get_latest_quote(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """Get latest quote for a specific stock.

    Args:
        symbol: Stock symbol

    Returns:
        Latest quote for the stock
    """
    symbol = symbol.upper()

    result = await db.execute(
        select(Quote, Stock.symbol, Stock.name)
        .join(Stock, Quote.stock_id == Stock.id)
        .where(Stock.symbol == symbol)
        .order_by(desc(Quote.timestamp))
        .limit(1)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail=f"No quotes found for {symbol}")

    quote = row[0]
    return QuoteWithSymbol(
        id=quote.id,
        stock_id=quote.stock_id,
        price=quote.price,
        open_price=quote.open_price,
        high=quote.high,
        low=quote.low,
        close=quote.close,
        volume=quote.volume,
        change=quote.change,
        change_percent=quote.change_percent,
        provider=quote.provider,
        timestamp=quote.timestamp,
        created_at=quote.created_at,
        symbol=row[1],
        name=row[2],
    )


@router.get("/{symbol}/history", response_model=list[HistoricalPriceResponse])
async def get_historical_prices(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(365, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get historical prices for a stock.

    Args:
        symbol: Stock symbol
        start_date: Start date (default: 1 year ago)
        end_date: End date (default: today)
        limit: Maximum number of records

    Returns:
        List of historical price data
    """
    symbol = symbol.upper()

    # Default date range
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    # Get stock
    result = await db.execute(select(Stock).where(Stock.symbol == symbol))
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get historical data
    result = await db.execute(
        select(HistoricalPrice)
        .where(HistoricalPrice.stock_id == stock.id)
        .where(HistoricalPrice.date >= start_date)
        .where(HistoricalPrice.date <= end_date)
        .order_by(HistoricalPrice.date)
        .limit(limit)
    )

    prices = result.scalars().all()
    return [
        HistoricalPriceResponse(
            date=p.date,
            open_price=p.open_price,
            high=p.high,
            low=p.low,
            close=p.close,
            adj_close=p.adj_close,
            volume=p.volume,
        )
        for p in prices
    ]


@router.get("/market/overview", response_model=MarketOverview)
async def get_market_overview(
    db: AsyncSession = Depends(get_db),
):
    """Get market overview with indices and top movers.

    Returns:
        Market overview including indices, gainers, losers, and most active
    """
    # Get latest quotes for all stocks with change data
    latest_subq = (
        select(Quote.stock_id, func.max(Quote.timestamp).label("max_ts"))
        .group_by(Quote.stock_id)
        .subquery()
    )

    quotes_query = (
        select(Quote, Stock)
        .join(Stock, Quote.stock_id == Stock.id)
        .join(
            latest_subq,
            and_(Quote.stock_id == latest_subq.c.stock_id, Quote.timestamp == latest_subq.c.max_ts),
        )
        .where(Quote.change_percent.isnot(None))
    )

    result = await db.execute(quotes_query)
    rows = result.fetchall()

    if not rows:
        return MarketOverview(
            indices=[],
            top_gainers=[],
            top_losers=[],
            most_active=[],
            last_updated=datetime.utcnow(),
        )

    # Separate indices and stocks
    indices = []
    stocks = []

    for quote, stock in rows:
        mover = MoverStock(
            symbol=stock.symbol,
            name=stock.name,
            name_cn=stock.name_cn,
            price=quote.price,
            change=quote.change,
            change_percent=quote.change_percent,
            volume=quote.volume,
        )

        if stock.symbol.startswith("^"):
            indices.append(
                IndexQuote(
                    symbol=stock.symbol,
                    name=stock.name,
                    price=quote.price,
                    change=quote.change,
                    change_percent=quote.change_percent,
                )
            )
        else:
            stocks.append(mover)

    # Sort for gainers, losers, most active
    stocks_by_change = sorted(
        [s for s in stocks if s.change_percent is not None],
        key=lambda x: x.change_percent,
        reverse=True,
    )

    stocks_by_volume = sorted(
        [s for s in stocks if s.volume is not None], key=lambda x: x.volume, reverse=True
    )

    return MarketOverview(
        indices=indices,
        top_gainers=stocks_by_change[:10],
        top_losers=stocks_by_change[-10:][::-1] if len(stocks_by_change) >= 10 else [],
        most_active=stocks_by_volume[:10],
        last_updated=datetime.utcnow(),
    )
