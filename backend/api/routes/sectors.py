"""Sector themes and stock relationships API routes.

GET /sectors/themes                — list all active sector themes (static + dynamic)
GET /sectors/themes/{name}         — detail for one sector (with top stocks)
GET /sectors/relationships/{symbol} — related stocks for a given symbol
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.database import get_db
from flowdesk_core.models import Quote, Stock
from flowdesk_core.models.sectors import SectorTheme, StockRelationship

router = APIRouter(
    prefix="/sectors",
    tags=["sectors"],
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _theme_summary(t: SectorTheme) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "name_cn": t.name_cn,
        "theme_type": t.theme_type,
        "icon_key": t.icon_key,
        "stock_count": t.stock_count,
        "avg_sentiment": t.avg_sentiment,
        "top_symbols": t.top_symbols or [],
        "top_themes": t.top_themes or [],
        "region": t.region,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("/themes")
async def list_sector_themes(
    theme_type: str | None = Query(default=None, description="Filter: static_gics | dynamic_ai"),
    db: AsyncSession = Depends(get_db),
):
    """List all active sector themes ordered by type then stock_count."""
    q = select(SectorTheme).where(SectorTheme.is_active == True)  # noqa: E712
    if theme_type:
        q = q.where(SectorTheme.theme_type == theme_type)
    # static_gics first, then dynamic_ai; within each type order by stock_count desc
    q = q.order_by(SectorTheme.theme_type, desc(SectorTheme.stock_count))

    result = await db.execute(q)
    themes = result.scalars().all()
    return [_theme_summary(t) for t in themes]


@router.get("/themes/{sector_name}")
async def get_sector_theme_detail(
    sector_name: str,
    theme_type: str = Query(default="static_gics"),
    db: AsyncSession = Depends(get_db),
):
    """Return full sector detail including description and top stocks with quotes."""
    result = await db.execute(
        select(SectorTheme).where(
            SectorTheme.name == sector_name,
            SectorTheme.theme_type == theme_type,
            SectorTheme.is_active == True,  # noqa: E712
        )
    )
    theme = result.scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail=f"Sector theme '{sector_name}' not found")

    # Fetch top 20 stocks in this sector with their latest quotes
    stocks_result = await db.execute(
        select(Stock, Quote)
        .outerjoin(
            Quote,
            and_(
                Quote.symbol == Stock.symbol,
                Quote.id
                == (
                    select(Quote.id)
                    .where(Quote.symbol == Stock.symbol)
                    .order_by(desc(Quote.timestamp))
                    .limit(1)
                    .correlate(Stock)
                    .scalar_subquery()
                ),
            ),
        )
        .where(
            Stock.sector == sector_name,
            Stock.is_active == True,  # noqa: E712
            Stock.market_cap.isnot(None),
        )
        .order_by(desc(Stock.market_cap))
        .limit(20)
    )
    stock_rows = stocks_result.all()

    stocks_out = []
    for stock, quote in stock_rows:
        stocks_out.append(
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "name_cn": stock.name_cn,
                "exchange": stock.exchange,
                "market_cap": stock.market_cap,
                "price": quote.price if quote else None,
                "change": quote.change if quote else None,
                "change_percent": quote.change_percent if quote else None,
            }
        )

    return {
        **_theme_summary(theme),
        "description": theme.description,
        "description_cn": theme.description_cn,
        "stocks": stocks_out,
    }


@router.get("/relationships/{symbol}")
async def get_stock_relationships(
    symbol: str,
    relationship_type: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Return related stocks for a given symbol, ordered by strength desc."""
    symbol = symbol.upper()

    q = select(StockRelationship).where(
        (StockRelationship.symbol_a == symbol) | (StockRelationship.symbol_b == symbol)
    )
    if relationship_type:
        q = q.where(StockRelationship.relationship_type == relationship_type)
    q = q.order_by(desc(StockRelationship.strength)).limit(limit)

    result = await db.execute(q)
    rels = result.scalars().all()

    out = []
    for r in rels:
        # Always return the "other" symbol relative to the requested one
        other = r.symbol_b if r.symbol_a == symbol else r.symbol_a
        out.append(
            {
                "symbol": other,
                "relationship_type": r.relationship_type,
                "strength": r.strength,
                "correlation_30d": r.correlation_30d,
                "correlation_90d": r.correlation_90d,
                "direction": r.direction,
                "source": r.source,
                "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            }
        )
    return out
