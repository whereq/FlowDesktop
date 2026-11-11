"""SimFill — immutable execution ledger (the source of truth for cash & positions).

Every fill atomically moves account cash and the position; positions/cash are the
derived current state, fills are append-only history.
See docs/design/RFC_STOCK_TRADING_SIMULATOR.md.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class SimFill(Base):
    __tablename__ = "sim_fills"
    __table_args__ = (Index("ix_sim_fills_account_created", "account_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<SimFill {self.side} {self.quantity} {self.symbol}@{self.price} cash={self.cash_delta}>"
