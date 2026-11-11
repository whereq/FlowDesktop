"""SimOrder — a simulator order (intent + lifecycle).

market: fill now (if market open) else queued to next open. limit: rests until the
price crosses (filled by the SimOrderMatcher collector job, Phase 2).
Statuses: pending → filled | cancelled | rejected | expired. No partial fills in v1
(filled_quantity/avg_fill_price exist for a non-breaking future add).
See docs/design/RFC_STOCK_TRADING_SIMULATOR.md.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

SIDE_BUY, SIDE_SELL = "buy", "sell"
TYPE_MARKET, TYPE_LIMIT = "market", "limit"
TIF_DAY, TIF_GTC = "day", "gtc"
STATUS_PENDING, STATUS_FILLED = "pending", "filled"
STATUS_CANCELLED, STATUS_REJECTED, STATUS_EXPIRED = "cancelled", "rejected", "expired"


class SimOrder(Base):
    __tablename__ = "sim_orders"
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="uq_sim_order_idem"),
        Index("ix_sim_orders_account_status", "account_id", "status"),
        Index("ix_sim_orders_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    order_type: Mapped[str] = mapped_column(String(6), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    tif: Mapped[str] = mapped_column(String(4), nullable=False, default=TIF_DAY)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=STATUS_PENDING)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(140), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=datetime.utcnow
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SimOrder {self.id} {self.side} {self.quantity} {self.symbol} {self.order_type} {self.status}>"
