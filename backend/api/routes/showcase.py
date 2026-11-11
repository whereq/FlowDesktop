"""Public showcase endpoint — no authentication required.

Returns a curated list of flagship stocks per exchange with their latest
quotes. Served to anonymous visitors as a preview of FlowDesktop's data.

When exchange/sector filters are supplied the endpoint falls back to the
top-25 stocks (by market cap) that match, instead of the curated list.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.stock import StockWithQuote
from flowdesk_core.database import get_db
from flowdesk_core.models import Quote, Stock

router = APIRouter(prefix="/showcase", tags=["showcase"])

# Mirror of stocks.py — maps raw DB exchange codes to canonical codes.
# Used to expand a canonical filter (e.g. "NYQ") to all stored variants
# (e.g. "NYSE", "NYS") so the WHERE clause matches what is actually in the DB.
_EXCHANGE_CANONICAL: dict[str, str] = {
    "SHH": "SSE",
    "SHG": "SSE",
    "SHZ": "SZSE",
    "SZE": "SZSE",
    "NYSE": "NYQ",
    "NYS": "NYQ",
    "NYA": "NYQ",
    "NYB": "NYQ",
    "NASDAQ": "NMS",
    "NIM": "NMS",
    "TOR": "TSX",
    "TXS": "TSX",
}


def _expand_exchanges(canonical_codes: list[str]) -> list[str]:
    """Return canonical codes plus every stored variant that maps to them."""
    aliases: dict[str, list[str]] = {}
    for variant, canonical in _EXCHANGE_CANONICAL.items():
        aliases.setdefault(canonical, []).append(variant)
    expanded: list[str] = []
    for code in canonical_codes:
        expanded.append(code)
        expanded.extend(aliases.get(code, []))
    return expanded


# Flagship symbols shown to anonymous visitors (no filters).
# Ordered by global brand recognition within each exchange.
_SHOWCASE_SYMBOLS: list[str] = [
    # US — NYSE / NASDAQ
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "JPM",
    "V",
    "JNJ",
    # Canada — TSX
    "RY.TO",
    "TD.TO",
    "ENB.TO",
    "CNQ.TO",
    "BNS.TO",
    # China — SSE (Shanghai)
    "600519.SS",
    "601318.SS",
    "600036.SS",
    "601166.SS",
    "600900.SS",
    # China — SZSE (Shenzhen)
    "000858.SZ",
    "000333.SZ",
    "002594.SZ",
    "300750.SZ",
    "000002.SZ",
]

_ORDER: dict[str, int] = {sym: i for i, sym in enumerate(_SHOWCASE_SYMBOLS)}

# Exchange codes whose stocks are represented in the curated list.
# Used to map filter selections back to the right curated subset.
_EXCHANGE_GROUPS: dict[str, list[str]] = {
    "NYQ": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "V", "JNJ"],
    "NMS": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "V", "JNJ"],
    "NGM": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "V", "JNJ"],
    "TSX": ["RY.TO", "TD.TO", "ENB.TO", "CNQ.TO", "BNS.TO"],
    "TOR": ["RY.TO", "TD.TO", "ENB.TO", "CNQ.TO", "BNS.TO"],
    "SSE": ["600519.SS", "601318.SS", "600036.SS", "601166.SS", "600900.SS"],
    "SHH": ["600519.SS", "601318.SS", "600036.SS", "601166.SS", "600900.SS"],
    "SZSE": ["000858.SZ", "000333.SZ", "002594.SZ", "300750.SZ", "000002.SZ"],
    "SHZ": ["000858.SZ", "000333.SZ", "002594.SZ", "300750.SZ", "000002.SZ"],
}


async def _attach_latest_quotes(stocks: list[Stock], db: AsyncSession) -> list[StockWithQuote]:
    """Efficiently fetch latest quote for each stock using individual lookups.

    Much faster than DISTINCT ON over the entire quotes table — only touches
    the rows needed via the (stock_id, timestamp DESC) index.
    """
    if not stocks:
        return []

    stock_ids = [s.id for s in stocks]

    # Use a correlated subquery approach: for each stock_id in our small set,
    # grab the latest quote row via the composite index.
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


@router.get("", response_model=list[StockWithQuote])
async def get_showcase_stocks(
    exchanges: list[str] | None = Query(default=None),
    sector: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return flagship stocks for anonymous visitors.

    No authentication required.

    - **No filters**: returns the curated 25 flagship symbols (5 per exchange).
    - **With filters**: returns up to 25 active stocks matching the selected
      exchanges/sector, ordered by market cap descending.
    """
    if exchanges or sector:
        # Filtered mode — first get the 25 matching stock IDs (fast)
        conditions: list = [Stock.is_active.is_(True)]
        if exchanges:
            conditions.append(Stock.exchange.in_(_expand_exchanges(exchanges)))
        if sector:
            conditions.append(Stock.sector == sector)

        stock_result = await db.execute(
            select(Stock).where(and_(*conditions)).order_by(desc(Stock.market_cap)).limit(25)
        )
        stocks = list(stock_result.scalars().all())
        return await _attach_latest_quotes(stocks, db)

    # Default mode — curated flagship list
    stock_result = await db.execute(select(Stock).where(Stock.symbol.in_(_SHOWCASE_SYMBOLS)))
    stocks = list(stock_result.scalars().all())
    results = await _attach_latest_quotes(stocks, db)
    return sorted(results, key=lambda s: _ORDER.get(s.symbol, 999))
