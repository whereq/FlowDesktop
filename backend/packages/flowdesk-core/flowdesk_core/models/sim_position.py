"""SimPosition — a simulator account's net-long holding of one symbol (derived state).

Maintained transactionally with each fill (see SimulationService.execute_fill).
Long-only in v1. See docs/design/RFC_STOCK_TRADING_SIMULATOR.md.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class SimPosition(Base):
    __tablename__ = "sim_positions"
    __table_args__ = (UniqueConstraint("account_id", "symbol", name="uq_sim_position"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<SimPosition acct={self.account_id} {self.symbol} qty={self.quantity}@{self.avg_cost}>"
