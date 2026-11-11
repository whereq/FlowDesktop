"""Market Intelligence API routes.

GET /intelligence/news           — recent news items (paginated)
GET /intelligence/signals        — processed signals (paginated, filterable)
GET /intelligence/sector/{name}  — latest sector intelligence for one GICS sector
GET /intelligence/sectors        — all sector intelligence for today (summary list)
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import get_current_user
from flowdesk_core.database import get_db
from flowdesk_core.models.market_intelligence import (
    MarketNewsItem,
    MarketSignal,
    SectorIntelligence,
)

router = APIRouter(
    prefix="/intelligence",
    tags=["intelligence"],
    dependencies=[Depends(get_current_user)],
)


# ─── News ─────────────────────────────────────────────────────────────────────


@router.get("/news")
async def get_news(
    hours: int = Query(default=24, ge=1, le=168, description="Look-back window in hours"),
    source: str | None = Query(
        default=None, description="Filter by source (e.g. polygon, eastmoney)"
    ),
    region: str | None = Query(default=None, description="Filter by region code (e.g. US, CN)"),
    language: str | None = Query(default=None, description="Filter by language (en, zh)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return recent news items from the market_news_items table."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    q = select(MarketNewsItem).where(MarketNewsItem.published_at >= cutoff)
    if source:
        q = q.where(MarketNewsItem.source == source)
    if region:
        q = q.where(MarketNewsItem.region == region)
    if language:
        q = q.where(MarketNewsItem.language == language)

    q = q.order_by(desc(MarketNewsItem.published_at)).offset(offset).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()

    return [
        {
            "id": item.id,
            "source": item.source,
            "source_id": item.source_id,
            "title": item.title,
            "summary": item.summary,
            "url": item.url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "region": item.region,
            "language": item.language,
            "raw_sentiment": item.raw_sentiment,
            "is_processed": item.is_processed,
        }
        for item in items
    ]


# ─── Signals ──────────────────────────────────────────────────────────────────


@router.get("/signals")
async def get_signals(
    hours: int = Query(default=24, ge=1, le=168),
    signal_type: str | None = Query(default=None),
    region: str | None = Query(
        default=None, description="Filter signals whose regions array contains this code"
    ),
    sector: str | None = Query(
        default=None, description="Filter signals whose sectors_affected contains this sector"
    ),
    symbol: str | None = Query(
        default=None, description="Filter signals mentioning or impacting this symbol"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return processed AI signals from the market_signals table."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    q = select(MarketSignal).where(MarketSignal.processed_at >= cutoff)
    if signal_type:
        q = q.where(MarketSignal.signal_type == signal_type)
    if region:
        # PostgreSQL: array contains element
        q = q.where(MarketSignal.regions.contains([region]))
    if sector:
        q = q.where(MarketSignal.sectors_affected.contains([sector]))
    if symbol:
        q = q.where(
            MarketSignal.symbols_mentioned.contains([symbol])
            | MarketSignal.symbols_impacted.contains([symbol])
        )

    q = q.order_by(desc(MarketSignal.processed_at)).offset(offset).limit(limit)
    result = await db.execute(q)
    signals = result.scalars().all()

    return [
        {
            "id": s.id,
            "news_item_id": s.news_item_id,
            "signal_type": s.signal_type,
            "sentiment": s.sentiment,
            "confidence": s.confidence,
            "impact_horizon": s.impact_horizon,
            "regions": s.regions,
            "sectors_affected": s.sectors_affected,
            "symbols_mentioned": s.symbols_mentioned,
            "symbols_impacted": s.symbols_impacted,
            "impact_direction": s.impact_direction,
            "theme_tags": s.theme_tags,
            "summary_en": s.summary_en,
            "summary_zh": s.summary_zh,
            "processed_at": s.processed_at.isoformat() if s.processed_at else None,
            "model_used": s.model_used,
        }
        for s in signals
    ]


# ─── Sector Intelligence ───────────────────────────────────────────────────────


@router.get("/sectors")
async def get_sector_intelligence_list(
    intel_date: date | None = Query(default=None, description="Date (default: today)"),
    region: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return today's sector intelligence summary list (all sectors × regions)."""
    if intel_date is None:
        intel_date = date.today()

    q = select(SectorIntelligence).where(SectorIntelligence.intel_date == intel_date)
    if region:
        q = q.where(SectorIntelligence.region == region)
    q = q.order_by(SectorIntelligence.sector, SectorIntelligence.region)

    result = await db.execute(q)
    rows = result.scalars().all()

    return [
        {
            "id": row.id,
            "sector": row.sector,
            "region": row.region,
            "intel_date": row.intel_date.isoformat() if row.intel_date else None,
            "signal_count": row.signal_count,
            "avg_sentiment": row.avg_sentiment,
            "bullish_count": row.bullish_count,
            "bearish_count": row.bearish_count,
            "top_themes": row.top_themes,
            # Omit narrative here — use /sector/{name} for full detail
        }
        for row in rows
    ]


@router.get("/sector/{sector_name}")
async def get_sector_intelligence_detail(
    sector_name: str,
    region: str = Query(default="US"),
    intel_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return full sector intelligence detail including narrative for one sector+region."""
    if intel_date is None:
        intel_date = date.today()

    result = await db.execute(
        select(SectorIntelligence).where(
            SectorIntelligence.sector == sector_name,
            SectorIntelligence.region == region,
            SectorIntelligence.intel_date == intel_date,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        # Try the most recent available record for this sector+region
        result = await db.execute(
            select(SectorIntelligence)
            .where(
                SectorIntelligence.sector == sector_name,
                SectorIntelligence.region == region,
            )
            .order_by(desc(SectorIntelligence.intel_date))
            .limit(1)
        )
        row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No intelligence found for sector '{sector_name}' / region '{region}'",
        )

    return {
        "id": row.id,
        "sector": row.sector,
        "region": row.region,
        "intel_date": row.intel_date.isoformat() if row.intel_date else None,
        "signal_count": row.signal_count,
        "avg_sentiment": row.avg_sentiment,
        "bullish_count": row.bullish_count,
        "bearish_count": row.bearish_count,
        "top_themes": row.top_themes,
        "narrative": row.narrative,
        "key_signal_ids": row.key_signal_ids,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
