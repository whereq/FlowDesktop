"""Trading simulator API (paper trading) — owner-scoped, /me/sim/*.

Thin HTTP layer over SimulationService (all trading logic lives there).
See docs/design/RFC_STOCK_TRADING_SIMULATOR.md §6.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.market_rules import MARKET_RULES
from api.services.simulation import sim_service
from flowdesk.entitlements import limit_for, roles_from_claims, tier_label
from flowdesk_core.auth import CurrentUser
from flowdesk_core.config import get_settings
from flowdesk_core.database import get_db
from flowdesk_core.models.sim_account import SimAccount
from flowdesk_core.models.sim_fill import SimFill
from flowdesk_core.models.sim_order import SimOrder
from flowdesk_core.models.sim_snapshot import SimSnapshot
from flowdesk_core.models.stock import Stock

router = APIRouter(prefix="/me/sim", tags=["simulator"])
settings = get_settings()


class AccountIn(BaseModel):
    name: str
    currency: str
    initial_balance: Decimal


class ResetIn(BaseModel):
    initial_balance: Decimal | None = None


class OrderIn(BaseModel):
    symbol: str
    side: str
    order_type: str = "market"
    quantity: Decimal
    limit_price: Decimal | None = None
    tif: str = "day"
    idempotency_key: str | None = None


def _summary(a: SimAccount) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "currency": a.currency,
        "cash_balance": str(a.cash_balance),
        "initial_balance": str(a.initial_balance),
        "is_active": a.is_active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _order_out(o: SimOrder) -> dict:
    return {
        "id": o.id,
        "symbol": o.symbol,
        "side": o.side,
        "order_type": o.order_type,
        "quantity": str(o.quantity),
        "limit_price": str(o.limit_price) if o.limit_price is not None else None,
        "tif": o.tif,
        "status": o.status,
        "filled_quantity": str(o.filled_quantity),
        "avg_fill_price": str(o.avg_fill_price) if o.avg_fill_price is not None else None,
        "reject_reason": o.reject_reason,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "filled_at": o.filled_at.isoformat() if o.filled_at else None,
    }


def _guard_enabled():
    if not settings.sim_enabled:
        raise HTTPException(404, "Simulator is disabled")


async def _own_account(db, uid, account_id) -> SimAccount:
    acct = await sim_service.get_account(db, uid, account_id)
    if acct is None or not acct.is_active:
        raise HTTPException(404, "Account not found")
    return acct


@router.post("/accounts")
async def create_account(
    body: AccountIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    currency = body.currency.strip().upper()
    if currency not in MARKET_RULES:
        raise HTTPException(400, f"Unsupported currency. One of: {', '.join(sorted(MARKET_RULES))}")
    if body.initial_balance <= 0 or body.initial_balance > settings.sim_max_initial_balance:
        raise HTTPException(
            400, f"initial_balance must be between 0 and {settings.sim_max_initial_balance}"
        )
    if not body.name.strip():
        raise HTTPException(400, "name is required")

    roles = roles_from_claims(current_user)
    cap = limit_for(roles, "sim_accounts")
    if await sim_service.count_accounts(db, uid) >= cap:
        raise HTTPException(
            402,
            f"Your {tier_label(roles)} plan allows {cap} simulator account(s). Upgrade for more.",
        )

    try:
        acct = await sim_service.create_account(db, uid, body.name, currency, body.initial_balance)
    except Exception:
        await db.rollback()
        raise HTTPException(409, "An account with that name already exists")
    return _summary(acct)


@router.get("/accounts")
async def list_accounts(
    current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    return [_summary(a) for a in await sim_service.list_accounts(db, uid)]


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    acct = await _own_account(db, uid, account_id)
    return await sim_service.value_account(db, acct)


@router.post("/accounts/{account_id}/reset")
async def reset_account(
    account_id: int, body: ResetIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    acct = await _own_account(db, uid, account_id)
    bal = body.initial_balance if body.initial_balance is not None else acct.initial_balance
    if bal <= 0 or bal > settings.sim_max_initial_balance:
        raise HTTPException(400, "invalid initial_balance")
    acct = await sim_service.reset_account(db, acct, bal)
    return _summary(acct)


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    acct = await _own_account(db, uid, account_id)
    await sim_service.deactivate_account(db, acct)


@router.post("/accounts/{account_id}/orders")
async def place_order(
    account_id: int, body: OrderIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    await _own_account(db, uid, account_id)
    try:
        order = await sim_service.place_order(
            db,
            uid,
            account_id,
            body.symbol,
            body.side,
            body.order_type,
            body.quantity,
            limit_price=body.limit_price,
            tif=body.tif,
            idempotency_key=body.idempotency_key,
        )
    except LookupError:
        raise HTTPException(404, "Account not found")
    return _order_out(order)


@router.get("/accounts/{account_id}/orders")
async def list_orders(
    account_id: int,
    current_user: CurrentUser,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    await _own_account(db, uid, account_id)
    stmt = select(SimOrder).where(SimOrder.account_id == account_id)
    if status:
        stmt = stmt.where(SimOrder.status == status)
    stmt = stmt.order_by(SimOrder.created_at.desc()).limit(200)
    return [_order_out(o) for o in (await db.execute(stmt)).scalars().all()]


@router.delete("/accounts/{account_id}/orders/{order_id}")
async def cancel_order(
    account_id: int, order_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    await _own_account(db, uid, account_id)
    order = await sim_service.cancel_order(db, uid, account_id, order_id)
    if order is None:
        raise HTTPException(404, "Order not found")
    return _order_out(order)


@router.get("/accounts/{account_id}/positions")
async def positions(
    account_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    acct = await _own_account(db, uid, account_id)
    return (await sim_service.value_account(db, acct))["positions"]


@router.get("/accounts/{account_id}/fills")
async def fills(
    account_id: int, current_user: CurrentUser, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    _guard_enabled()
    uid = UUID(current_user["sub"])
    await _own_account(db, uid, account_id)
    limit = max(1, min(int(limit or 100), 500))
    rows = (
        (
            await db.execute(
                select(SimFill)
                .where(SimFill.account_id == account_id)
                .order_by(SimFill.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "symbol": f.symbol,
            "side": f.side,
            "quantity": str(f.quantity),
            "price": str(f.price),
            "fee": str(f.fee),
            "cash_delta": str(f.cash_delta),
            "realized_pnl": str(f.realized_pnl),
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
    ]


@router.get("/accounts/{account_id}/snapshots")
async def snapshots(
    account_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    """Equity curve. Empty until the SimSnapshot collector job lands (Phase 2)."""
    _guard_enabled()
    uid = UUID(current_user["sub"])
    await _own_account(db, uid, account_id)
    rows = (
        (
            await db.execute(
                select(SimSnapshot)
                .where(SimSnapshot.account_id == account_id)
                .order_by(SimSnapshot.ts)
            )
        )
        .scalars()
        .all()
    )
    return [{"ts": s.ts.isoformat(), "equity": str(s.equity)} for s in rows]


@router.get("/accounts/{account_id}/tradable")
async def tradable(
    account_id: int, current_user: CurrentUser, q: str = "", db: AsyncSession = Depends(get_db)
) -> list[dict]:
    """Search the account-currency universe (stocks tradable in this account)."""
    _guard_enabled()
    uid = UUID(current_user["sub"])
    acct = await _own_account(db, uid, account_id)
    stmt = select(Stock).where(Stock.currency == acct.currency, Stock.is_active == True)  # noqa: E712
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Stock.symbol.ilike(like), Stock.name.ilike(like)))
    stmt = stmt.order_by(Stock.symbol).limit(25)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"symbol": s.symbol, "name": s.name, "exchange": s.exchange} for s in rows]
