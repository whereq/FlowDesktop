"""Watchlist endpoints.

GET    /api/v1/me/watchlist         — list symbols (ordered)
POST   /api/v1/me/watchlist         — add a symbol
DELETE /api/v1/me/watchlist/{symbol} — remove a symbol
PUT    /api/v1/me/watchlist         — replace entire list (bulk sync)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.watchlist import WatchlistItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me/watchlist", tags=["watchlist"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class WatchlistResponse(BaseModel):
    symbols: list[str]


class WatchlistAddRequest(BaseModel):
    symbol: str


class WatchlistBulkRequest(BaseModel):
    symbols: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _uid(current_user: dict) -> UUID:
    return UUID(current_user["sub"])


async def _get_symbols(db: AsyncSession, uid: UUID) -> list[str]:
    result = await db.execute(
        select(WatchlistItem.symbol)
        .where(WatchlistItem.keycloak_id == uid)
        .order_by(WatchlistItem.sort_order, WatchlistItem.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return the user's watchlist symbols in order."""
    symbols = await _get_symbols(db, _uid(current_user))
    return WatchlistResponse(symbols=symbols)


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Add a symbol to the watchlist. Idempotent — duplicate adds are ignored."""
    uid = _uid(current_user)
    symbol = body.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    # Check if already exists
    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.keycloak_id == uid,
            WatchlistItem.symbol == symbol,
        )
    )
    if existing.scalar_one_or_none() is None:
        # Get next sort_order
        max_order = await db.execute(
            select(func.coalesce(func.max(WatchlistItem.sort_order), -1)).where(
                WatchlistItem.keycloak_id == uid
            )
        )
        next_order = (max_order.scalar() or 0) + 1
        db.add(WatchlistItem(keycloak_id=uid, symbol=symbol, sort_order=next_order))
        await db.commit()

    symbols = await _get_symbols(db, uid)
    return WatchlistResponse(symbols=symbols)


@router.delete("/{symbol}", response_model=WatchlistResponse)
async def remove_from_watchlist(
    symbol: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Remove a symbol from the watchlist."""
    uid = _uid(current_user)
    await db.execute(
        delete(WatchlistItem).where(
            WatchlistItem.keycloak_id == uid,
            WatchlistItem.symbol == symbol.upper(),
        )
    )
    await db.commit()
    symbols = await _get_symbols(db, uid)
    return WatchlistResponse(symbols=symbols)


@router.put("", response_model=WatchlistResponse)
async def replace_watchlist(
    body: WatchlistBulkRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Replace the entire watchlist. Used for bulk sync (e.g., merging localStorage on login)."""
    uid = _uid(current_user)

    # Delete all existing
    await db.execute(delete(WatchlistItem).where(WatchlistItem.keycloak_id == uid))

    # Insert new list with order preserved
    seen: set[str] = set()
    for i, sym in enumerate(body.symbols):
        s = sym.upper().strip()
        if s and s not in seen:
            seen.add(s)
            db.add(WatchlistItem(keycloak_id=uid, symbol=s, sort_order=i))

    await db.commit()
    symbols = await _get_symbols(db, uid)
    return WatchlistResponse(symbols=symbols)
