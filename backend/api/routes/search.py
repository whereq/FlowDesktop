"""Search and utility API routes."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.quote import ProviderStatusResponse
from flowdesk_collector.provider_registry import list_providers
from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db

router = APIRouter(tags=["utilities"])


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "flowdesk-api",
    }


@router.get("/providers/status", response_model=list[ProviderStatusResponse])
async def get_provider_status(_: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Get status of all data providers.

    Returns:
        List of provider statuses with usage info
    """
    statuses = await list_providers(db)

    return [ProviderStatusResponse(**s) for s in statuses]


@router.get("/stats")
async def get_stats(_: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Get database statistics.

    Returns:
        Stats including stock count, quote count, etc.
    """
    from sqlalchemy import func

    from flowdesk_core.models import HistoricalPrice, Quote, Stock

    stock_count = await db.scalar(select(func.count(Stock.id)))
    quote_count = await db.scalar(select(func.count(Quote.id)))
    historical_count = await db.scalar(select(func.count(HistoricalPrice.id)))

    latest_quote = await db.scalar(select(func.max(Quote.timestamp)))

    return {
        "stocks": stock_count,
        "quotes": quote_count,
        "historical_records": historical_count,
        "latest_quote_time": latest_quote.isoformat() if latest_quote else None,
    }
