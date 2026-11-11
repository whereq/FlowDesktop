"""Stock-related API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.stock import StockSearchResult, StockWithQuote
from flowdesk_core.auth import get_current_user
from flowdesk_core.database import get_db
from flowdesk_core.models import Quote, Stock

router = APIRouter(prefix="/stocks", tags=["stocks"])

# Maps variant exchange codes (from Yahoo, TuShare, etc.) to canonical codes
# used throughout the app and i18n keys.
_EXCHANGE_CANONICAL: dict[str, str] = {
    # Chinese exchanges
    "SHH": "SSE",
    "SHG": "SSE",
    "SHZ": "SZSE",
    "SZE": "SZSE",
    # US NYSE variants
    "NYSE": "NYQ",
    "NYS": "NYQ",
    "NYA": "NYQ",
    "NYB": "NYQ",
    # NASDAQ variants
    "NASDAQ": "NMS",
    "NIM": "NMS",
    # Canadian
    "TOR": "TSX",
    "TXS": "TSX",
}


def _canonical_exchange(code: str | None) -> str | None:
    """Return the canonical exchange code, normalising known variants."""
    if code is None:
        return None
    return _EXCHANGE_CANONICAL.get(code, code)


@router.get("", response_model=list[StockWithQuote])
async def list_stocks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    sector: str | None = None,
    exchanges: list[str] | None = Query(default=None),
    symbols: list[str] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    """List all stocks with their latest quotes.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        sector: Filter by sector
        exchanges: Filter by exchange codes
        symbols: Filter by specific symbol list (e.g. for watchlist)

    Returns:
        List of stocks with latest quote data
    """
    # Step 1: Get the matching stock IDs (fast — uses indexes on exchange, sector)
    stock_query = select(Stock).where(Stock.is_active.is_(True))

    if sector:
        stock_query = stock_query.where(Stock.sector == sector)

    if exchanges:
        _aliases: dict[str, list[str]] = {}
        for variant, canonical in _EXCHANGE_CANONICAL.items():
            _aliases.setdefault(canonical, []).append(variant)
        expanded: list[str] = []
        for ex in exchanges:
            expanded.append(ex)
            expanded.extend(_aliases.get(ex, []))
        stock_query = stock_query.where(Stock.exchange.in_(expanded))

    if symbols:
        stock_query = stock_query.where(Stock.symbol.in_(symbols))

    stock_query = stock_query.order_by(Stock.symbol).offset(skip).limit(limit)
    stock_result = await db.execute(stock_query)
    stock_list = list(stock_result.scalars().all())

    if not stock_list:
        return []

    # Step 2: Get latest quote for only the matched stocks (fast — small IN list)
    stock_ids = [s.id for s in stock_list]
    latest_quote_subq = (
        select(
            Quote.stock_id,
            Quote.price,
            Quote.change,
            Quote.change_percent,
            Quote.volume,
            Quote.timestamp.label("quote_timestamp"),
        )
        .where(Quote.stock_id.in_(stock_ids))
        .distinct(Quote.stock_id)
        .order_by(Quote.stock_id, desc(Quote.timestamp))
        .subquery()
    )

    result = await db.execute(
        select(
            Stock,
            latest_quote_subq.c.price,
            latest_quote_subq.c.change,
            latest_quote_subq.c.change_percent,
            latest_quote_subq.c.volume,
            latest_quote_subq.c.quote_timestamp,
        )
        .outerjoin(latest_quote_subq, Stock.id == latest_quote_subq.c.stock_id)
        .where(Stock.id.in_(stock_ids))
        .order_by(Stock.symbol)
    )

    return [
        StockWithQuote(
            id=row[0].id,
            symbol=row[0].symbol,
            name=row[0].name,
            name_cn=row[0].name_cn,
            exchange=row[0].exchange,
            sector=row[0].sector,
            industry=row[0].industry,
            market_cap=row[0].market_cap,
            created_at=row[0].created_at,
            updated_at=row[0].updated_at,
            price=row[1],
            change=row[2],
            change_percent=row[3],
            volume=row[4],
            quote_timestamp=row[5],
        )
        for row in result.fetchall()
    ]


@router.get("/sectors", response_model=list[str])
async def list_sectors(db: AsyncSession = Depends(get_db)):
    """Get list of all unique sectors."""
    result = await db.execute(
        select(Stock.sector).where(Stock.sector.isnot(None)).distinct().order_by(Stock.sector)
    )
    return [row[0] for row in result.fetchall()]


@router.get("/exchanges", response_model=list[str])
async def list_exchanges(db: AsyncSession = Depends(get_db)):
    """Get list of all unique exchanges, normalised to canonical codes.

    Excludes index-only exchange codes (CXI, DJI, SNP, WCB, NIM, etc.) that
    appear because market-index symbols (^GSPC, ^DJI …) are stored in the
    stocks table.  Those codes are meaningless for stock filtering.
    """
    # Index symbols start with "^" — their exchange codes are not real exchanges
    result = await db.execute(
        select(Stock.exchange)
        .where(Stock.exchange.isnot(None))
        .where(~Stock.symbol.startswith("^"))
        .distinct()
    )
    raw_codes = [row[0] for row in result.fetchall()]
    # Normalise variants → canonical, deduplicate, then sort
    canonical = sorted({_canonical_exchange(c) for c in raw_codes})
    return canonical


@router.get("/search", response_model=list[StockSearchResult])
async def search_stocks(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    """Search stocks by symbol or name.

    Args:
        q: Search query (symbol or name)
        limit: Maximum number of results

    Returns:
        List of matching stocks
    """
    search_term = f"%{q.upper()}%"

    result = await db.execute(
        select(Stock)
        .where(
            (Stock.symbol.ilike(search_term))
            | (Stock.name.ilike(f"%{q}%"))
            | (Stock.name_cn.ilike(f"%{q}%"))
        )
        .order_by(
            # Prioritize exact symbol matches
            (Stock.symbol == q.upper()).desc(),
            # Then symbol starts with query
            Stock.symbol.ilike(f"{q.upper()}%").desc(),
            Stock.symbol,
        )
        .limit(limit)
    )

    stocks = result.scalars().all()
    return [
        StockSearchResult(
            symbol=s.symbol,
            name=s.name,
            name_cn=s.name_cn,
            exchange=s.exchange,
        )
        for s in stocks
    ]


@router.get("/{symbol}", response_model=StockWithQuote)
async def get_stock(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    """Get a single stock by symbol with latest quote.

    Args:
        symbol: Stock symbol (e.g., AAPL)

    Returns:
        Stock details with latest quote
    """
    symbol = symbol.upper()

    # Get stock
    result = await db.execute(select(Stock).where(Stock.symbol == symbol))
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get latest quote
    quote_result = await db.execute(
        select(Quote).where(Quote.stock_id == stock.id).order_by(desc(Quote.timestamp)).limit(1)
    )
    quote = quote_result.scalar_one_or_none()

    return StockWithQuote(
        id=stock.id,
        symbol=stock.symbol,
        name=stock.name,
        name_cn=stock.name_cn,
        exchange=stock.exchange,
        currency=stock.currency,
        sector=stock.sector,
        industry=stock.industry,
        market_cap=stock.market_cap,
        created_at=stock.created_at,
        updated_at=stock.updated_at,
        price=quote.price if quote else None,
        change=quote.change if quote else None,
        change_percent=quote.change_percent if quote else None,
        volume=quote.volume if quote else None,
        quote_timestamp=quote.timestamp if quote else None,
    )


@router.get("/count/total")
async def get_stock_count(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(get_current_user),
):
    """Get total count of stocks in database."""
    result = await db.execute(select(func.count(Stock.id)))
    return {"count": result.scalar()}
