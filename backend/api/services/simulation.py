"""SimulationService — all trading-simulator domain logic.

Reused by the API routes, the collector jobs (Phase 2), and NOVA tools (Phase 4):
no trading logic lives anywhere else. Money is Decimal throughout; the fill path is
transactional with a row-lock on the account. Pure helpers (validate_order,
compute_fill, rounding) are unit-tested. See docs/design/RFC_STOCK_TRADING_SIMULATOR.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.market_rules import rules_for
from flowdesk_core.config import get_settings
from flowdesk_core.database import AsyncSessionLocal
from flowdesk_core.models.quote import Quote
from flowdesk_core.models.sim_account import SimAccount
from flowdesk_core.models.sim_fill import SimFill
from flowdesk_core.models.sim_order import (
    SIDE_BUY,
    SIDE_SELL,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_FILLED,
    STATUS_PENDING,
    STATUS_REJECTED,
    TIF_DAY,
    TYPE_LIMIT,
    TYPE_MARKET,
    SimOrder,
)
from flowdesk_core.models.sim_position import SimPosition
from flowdesk_core.models.sim_snapshot import SimSnapshot
from flowdesk_core.models.stock import Stock

logger = logging.getLogger(__name__)
settings = get_settings()

_CASH_Q = Decimal("0.0001")
_PRICE_Q = Decimal("0.000001")


def _dec(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def _round_cash(d: Decimal) -> Decimal:
    return _dec(d).quantize(_CASH_Q, rounding=ROUND_HALF_UP)


def _round_price(d: Decimal) -> Decimal:
    return _dec(d).quantize(_PRICE_Q, rounding=ROUND_HALF_UP)


# --- pure helpers (unit-tested) ---------------------------------------------


def validate_order(
    *,
    account_active: bool,
    account_currency: str,
    stock_active: bool,
    stock_currency: str,
    side: str,
    order_type: str,
    quantity,
    limit_price,
    ref_price,
    held_qty,
    cash_balance,
    lot: int,
    commission_bps: float = 0.0,
) -> str | None:
    """Return a rejection reason, or None if the order is valid."""
    if not account_active:
        return "account is inactive"
    if side not in (SIDE_BUY, SIDE_SELL):
        return "invalid side"
    if order_type not in (TYPE_MARKET, TYPE_LIMIT):
        return "invalid order type"
    if not stock_active:
        return "symbol is delisted or inactive"
    if (stock_currency or "").upper() != (account_currency or "").upper():
        return f"symbol trades in {stock_currency}; not tradable in a {account_currency} account"
    q = _dec(quantity)
    if q <= 0:
        return "quantity must be positive"
    if lot and (q % Decimal(lot) != 0):
        return f"quantity must be a multiple of {lot} (board lot)"
    if order_type == TYPE_LIMIT and (limit_price is None or _dec(limit_price) <= 0):
        return "limit orders require a positive limit price"
    if side == SIDE_BUY:
        px = (
            _dec(limit_price)
            if order_type == TYPE_LIMIT
            else (_dec(ref_price) if ref_price is not None else None)
        )
        if px is None:
            return "no recent price available for this symbol"
        est = q * px * (Decimal(1) + _dec(commission_bps) / Decimal(10000))
        if est > _dec(cash_balance):
            return "insufficient buying power"
    else:  # sell
        if q > _dec(held_qty):
            return "insufficient shares (shorting is not allowed)"
    return None


def limit_crosses(side: str, last, limit) -> bool:
    """True if a resting limit order should fill: buy fills at/below limit, sell at/above."""
    last, limit = _dec(last), _dec(limit)
    return last <= limit if side == SIDE_BUY else last >= limit


def _end_of_utc_day(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return datetime.combine(now.date(), time(23, 59, 59))


def compute_fill(
    side: str, quantity, price, commission_bps: float = 0.0, slippage_bps: float = 0.0
) -> dict:
    """Money math for one fill (pure). Returns exec_price/fee/cash_delta/gross."""
    q = _dec(quantity)
    p = _dec(price)
    slip = p * _dec(slippage_bps) / Decimal(10000)
    exec_price = _round_price(p + slip if side == SIDE_BUY else p - slip)
    gross = q * exec_price
    fee = _round_cash(gross * _dec(commission_bps) / Decimal(10000))
    cash_delta = _round_cash(-(gross + fee)) if side == SIDE_BUY else _round_cash(gross - fee)
    return {
        "exec_price": exec_price,
        "fee": fee,
        "cash_delta": cash_delta,
        "gross": _round_cash(gross),
    }


# --- service ----------------------------------------------------------------


class SimulationService:
    async def latest_prices(
        self, db: AsyncSession, symbols: list[str]
    ) -> dict[str, tuple[Decimal, datetime]]:
        if not symbols:
            return {}
        rows = (
            await db.execute(
                select(Stock.symbol, Quote.price, Quote.timestamp)
                .join(Stock, Quote.stock_id == Stock.id)
                .where(Stock.symbol.in_(symbols))
                .order_by(Stock.symbol, Quote.timestamp.desc())
                .distinct(Stock.symbol)
            )
        ).all()
        return {r.symbol: (_dec(r.price), r.timestamp) for r in rows}

    async def latest_price(self, db: AsyncSession, symbol: str):
        return (await self.latest_prices(db, [symbol])).get(symbol)

    # -- accounts --
    async def create_account(self, db, uid, name, currency, initial_balance) -> SimAccount:
        bal = _round_cash(initial_balance)
        acct = SimAccount(
            keycloak_id=uid,
            name=name.strip()[:80],
            currency=currency.strip().upper(),
            initial_balance=bal,
            cash_balance=bal,
            is_active=True,
        )
        db.add(acct)
        await db.commit()
        await db.refresh(acct)
        return acct

    async def list_accounts(self, db, uid) -> list[SimAccount]:
        return list(
            (
                await db.execute(
                    select(SimAccount)
                    .where(SimAccount.keycloak_id == uid, SimAccount.is_active == True)  # noqa: E712
                    .order_by(SimAccount.created_at)
                )
            )
            .scalars()
            .all()
        )

    async def get_account(self, db, uid, account_id, for_update=False) -> SimAccount | None:
        stmt = select(SimAccount).where(SimAccount.id == account_id, SimAccount.keycloak_id == uid)
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    async def reset_account(self, db, account: SimAccount, initial_balance) -> SimAccount:
        bal = _round_cash(initial_balance)
        # wipe positions/orders/fills for a clean restart; keep the account row.
        for model in (SimPosition, SimOrder, SimFill, SimSnapshot):
            for row in (
                (await db.execute(select(model).where(model.account_id == account.id)))
                .scalars()
                .all()
            ):
                await db.delete(row)
        account.initial_balance = bal
        account.cash_balance = bal
        await db.commit()
        await db.refresh(account)
        return account

    async def deactivate_account(self, db, account: SimAccount) -> None:
        account.is_active = False
        await db.commit()

    async def count_accounts(self, db, uid) -> int:
        return len(await self.list_accounts(db, uid))

    # -- orders --
    async def place_order(
        self,
        db,
        uid,
        account_id,
        symbol,
        side,
        order_type,
        quantity,
        limit_price=None,
        tif=TIF_DAY,
        idempotency_key=None,
    ) -> SimOrder:
        symbol = (symbol or "").strip().upper()
        side = (side or "").strip().lower()
        order_type = (order_type or "").strip().lower()
        tif = (tif or TIF_DAY).strip().lower()

        account = await self.get_account(db, uid, account_id, for_update=True)
        if account is None:
            raise LookupError("account not found")

        if idempotency_key:
            existing = (
                await db.execute(
                    select(SimOrder).where(
                        SimOrder.account_id == account_id,
                        SimOrder.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return existing

        stock = (await db.execute(select(Stock).where(Stock.symbol == symbol))).scalar_one_or_none()
        priced = await self.latest_price(db, symbol)
        ref_price = priced[0] if priced else None
        market_open = _is_open(stock.exchange) if stock else False
        # Stale-quote guard: while the market is open, an old quote isn't a fill price.
        if market_open and priced is not None:
            age_min = (datetime.utcnow() - priced[1]).total_seconds() / 60 if priced[1] else 0
            if age_min > settings.sim_quote_max_age_minutes:
                ref_price = None

        pos = (
            await db.execute(
                select(SimPosition)
                .where(SimPosition.account_id == account_id, SimPosition.symbol == symbol)
                .with_for_update()
            )
        ).scalar_one_or_none()
        held = pos.quantity if pos else Decimal(0)
        rules = rules_for(account.currency)

        reason = validate_order(
            account_active=account.is_active,
            account_currency=account.currency,
            stock_active=bool(stock and stock.is_active),
            stock_currency=(stock.currency if stock else ""),
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            ref_price=ref_price,
            held_qty=held,
            cash_balance=account.cash_balance,
            lot=rules.lot,
            commission_bps=settings.sim_commission_bps,
        )

        order = SimOrder(
            account_id=account_id,
            keycloak_id=uid,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=_dec(quantity),
            limit_price=(_dec(limit_price) if limit_price is not None else None),
            tif=tif,
            idempotency_key=idempotency_key,
            status=STATUS_PENDING,
        )
        if reason:
            order.status = STATUS_REJECTED
            order.reject_reason = reason
            db.add(order)
            await db.commit()
            await db.refresh(order)
            return order

        db.add(order)
        await db.flush()  # populate order.id for the fill

        # Market order: fill now if open with a fresh price; else it rests (queued to
        # next open) and the matcher fills it. Limit orders always rest; day limit
        # orders expire at end of the UTC day.
        if order_type == TYPE_MARKET and market_open and ref_price is not None:
            await self.execute_fill(db, order, account, pos, ref_price)
        elif order_type == TYPE_LIMIT and tif == TIF_DAY:
            order.expires_at = _end_of_utc_day()

        await db.commit()
        await db.refresh(order)
        return order

    # -- matcher & snapshots (collector jobs, Phase 2) --
    async def match_pending_orders(self) -> dict:
        """Fill resting limit orders that cross + queued market orders when their
        market is open; expire day orders past their deadline. Each order is
        processed in its own transaction under the account row-lock, with fresh
        affordability/holdings re-validation. No-op unless sim_enabled."""
        if not settings.sim_enabled:
            return {"filled": 0, "expired": 0, "rejected": 0}
        now = datetime.utcnow()
        filled = expired = rejected = 0

        async with AsyncSessionLocal() as s0:
            pending_ids = (
                (
                    await s0.execute(
                        select(SimOrder.id)
                        .where(SimOrder.status == STATUS_PENDING)
                        .order_by(SimOrder.created_at)
                    )
                )
                .scalars()
                .all()
            )

        for oid in pending_ids:
            async with AsyncSessionLocal() as db:
                order = (
                    await db.execute(
                        select(SimOrder)
                        .where(SimOrder.id == oid, SimOrder.status == STATUS_PENDING)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if order is None:
                    continue
                if order.expires_at and now > order.expires_at:
                    order.status = STATUS_EXPIRED
                    await db.commit()
                    expired += 1
                    continue

                stock = (
                    await db.execute(select(Stock).where(Stock.symbol == order.symbol))
                ).scalar_one_or_none()
                if stock is None or not stock.is_active:
                    order.status = STATUS_REJECTED
                    order.reject_reason = "symbol is delisted or inactive"
                    await db.commit()
                    rejected += 1
                    continue
                if not _is_open(stock.exchange):
                    continue  # market closed — queued/limit orders wait

                priced = await self.latest_price(db, order.symbol)
                if priced is None:
                    continue
                price, ts = priced
                if ts and (now - ts).total_seconds() / 60 > settings.sim_quote_max_age_minutes:
                    continue  # stale
                if order.order_type == TYPE_LIMIT and not limit_crosses(
                    order.side, price, order.limit_price
                ):
                    continue  # hasn't crossed yet

                account = (
                    await db.execute(
                        select(SimAccount)
                        .where(SimAccount.id == order.account_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if account is None or not account.is_active:
                    order.status = STATUS_REJECTED
                    order.reject_reason = "account inactive"
                    await db.commit()
                    rejected += 1
                    continue
                pos = (
                    await db.execute(
                        select(SimPosition)
                        .where(
                            SimPosition.account_id == account.id, SimPosition.symbol == order.symbol
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                held = pos.quantity if pos else Decimal(0)
                rules = rules_for(account.currency)
                reason = validate_order(
                    account_active=account.is_active,
                    account_currency=account.currency,
                    stock_active=True,
                    stock_currency=stock.currency,
                    side=order.side,
                    order_type=order.order_type,
                    quantity=order.quantity,
                    limit_price=order.limit_price,
                    ref_price=price,
                    held_qty=held,
                    cash_balance=account.cash_balance,
                    lot=rules.lot,
                    commission_bps=settings.sim_commission_bps,
                )
                if reason:
                    order.status = STATUS_REJECTED
                    order.reject_reason = f"at fill time: {reason}"
                    await db.commit()
                    rejected += 1
                    continue
                await self.execute_fill(db, order, account, pos, price)
                await db.commit()
                filled += 1

        return {"filled": filled, "expired": expired, "rejected": rejected}

    async def snapshot_all(self) -> int:
        """Mark-to-market every active account into sim_snapshots (one row per day)."""
        if not settings.sim_enabled:
            return 0
        ts = datetime.combine(datetime.utcnow().date(), time())  # midnight UTC today
        n = 0
        async with AsyncSessionLocal() as db:
            accounts = list(
                (
                    await db.execute(
                        select(SimAccount).where(SimAccount.is_active == True)  # noqa: E712
                    )
                )
                .scalars()
                .all()
            )
            for acct in accounts:
                v = await self.value_account(db, acct)
                vals = {
                    "cash": _dec(v["cash_balance"]),
                    "positions_value": _dec(v["positions_value"]),
                    "equity": _dec(v["equity"]),
                }
                await db.execute(
                    pg_insert(SimSnapshot)
                    .values(account_id=acct.id, ts=ts, **vals)
                    .on_conflict_do_update(constraint="uq_sim_snapshot", set_=vals)
                )
                n += 1
            await db.commit()
        return n

    async def execute_fill(
        self, db, order: SimOrder, account: SimAccount, pos: SimPosition | None, price
    ) -> None:
        """Atomically apply a fill: cash + position + immutable ledger + order status.
        Caller must hold the account row lock (place_order / matcher do)."""
        f = compute_fill(
            order.side,
            order.quantity,
            price,
            settings.sim_commission_bps,
            settings.sim_slippage_bps,
        )
        exec_price, fee, cash_delta = f["exec_price"], f["fee"], f["cash_delta"]
        realized = Decimal(0)

        if order.side == SIDE_BUY:
            if pos is None:
                db.add(
                    SimPosition(
                        account_id=order.account_id,
                        symbol=order.symbol,
                        quantity=order.quantity,
                        avg_cost=exec_price,
                        realized_pnl=Decimal(0),
                    )
                )
            else:
                new_qty = pos.quantity + order.quantity
                pos.avg_cost = _round_price(
                    (pos.quantity * pos.avg_cost + order.quantity * exec_price) / new_qty
                )
                pos.quantity = new_qty
        else:  # sell — validation guarantees pos exists with enough shares
            realized = _round_cash((exec_price - pos.avg_cost) * order.quantity)
            pos.quantity = pos.quantity - order.quantity
            pos.realized_pnl = pos.realized_pnl + realized
            if pos.quantity <= 0:
                await db.delete(pos)

        account.cash_balance = _round_cash(account.cash_balance + cash_delta)
        db.add(
            SimFill(
                order_id=order.id,
                account_id=order.account_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=exec_price,
                fee=fee,
                cash_delta=cash_delta,
                realized_pnl=realized,
            )
        )
        order.status = STATUS_FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = exec_price
        order.filled_at = datetime.utcnow()

    async def cancel_order(self, db, uid, account_id, order_id) -> SimOrder | None:
        order = (
            await db.execute(
                select(SimOrder).where(
                    SimOrder.id == order_id,
                    SimOrder.account_id == account_id,
                    SimOrder.keycloak_id == uid,
                )
            )
        ).scalar_one_or_none()
        if order is None:
            return None
        if order.status == STATUS_PENDING:
            order.status = STATUS_CANCELLED
            await db.commit()
            await db.refresh(order)
        return order

    # -- valuation --
    async def value_account(self, db, account: SimAccount) -> dict:
        positions = list(
            (await db.execute(select(SimPosition).where(SimPosition.account_id == account.id)))
            .scalars()
            .all()
        )
        prices = await self.latest_prices(db, [p.symbol for p in positions])

        pos_out: list[dict] = []
        positions_value = Decimal(0)
        for p in positions:
            pr = prices.get(p.symbol)
            price = pr[0] if pr else None
            mv = _round_cash(p.quantity * price) if price is not None else Decimal(0)
            positions_value += mv
            upnl = (
                _round_cash((price - p.avg_cost) * p.quantity) if price is not None else Decimal(0)
            )
            cost = p.avg_cost * p.quantity
            pos_out.append(
                {
                    "symbol": p.symbol,
                    "quantity": str(p.quantity),
                    "avg_cost": str(p.avg_cost),
                    "price": str(price) if price is not None else None,
                    "market_value": str(mv),
                    "unrealized_pnl": str(upnl),
                    "unrealized_pnl_pct": round(float(upnl / cost * 100), 2) if cost else 0.0,
                    "as_of": pr[1].isoformat() if pr and pr[1] else None,
                }
            )

        positions_value = _round_cash(positions_value)
        equity = _round_cash(account.cash_balance + positions_value)
        total_return = _round_cash(equity - account.initial_balance)
        for pd in pos_out:
            pd["weight_pct"] = (
                round(float(_dec(pd["market_value"]) / equity * 100), 2) if equity > 0 else 0.0
            )

        # day_change from the most recent prior snapshot (0 until snapshots exist, Phase 2)
        prev = (
            await db.execute(
                select(SimSnapshot.equity)
                .where(SimSnapshot.account_id == account.id)
                .order_by(SimSnapshot.ts.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        day_change = _round_cash(equity - prev) if prev is not None else Decimal(0)

        return {
            "id": account.id,
            "name": account.name,
            "currency": account.currency,
            "cash_balance": str(_round_cash(account.cash_balance)),
            "initial_balance": str(account.initial_balance),
            "positions_value": str(positions_value),
            "equity": str(equity),
            "total_return": str(total_return),
            "total_return_pct": round(float(total_return / account.initial_balance * 100), 2)
            if account.initial_balance
            else 0.0,
            "day_change": str(day_change),
            "day_change_pct": round(float(day_change / prev * 100), 2) if prev else 0.0,
            "positions": pos_out,
        }


def _is_open(exchange: str | None) -> bool:
    if not exchange:
        return False
    try:
        from flowdesk_collector.market_hours import is_market_open

        return is_market_open(exchange)
    except Exception:
        return False


sim_service = SimulationService()
