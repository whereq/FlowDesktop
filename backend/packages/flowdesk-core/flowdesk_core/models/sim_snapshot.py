"""SimSnapshot — periodic mark-to-market of an account's equity (the equity curve).

Written by the SimSnapshot collector job (Phase 2). Powers the equity-curve chart
and day-change. See docs/design/RFC_STOCK_TRADING_SIMULATOR.md.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class SimSnapshot(Base):
    __tablename__ = "sim_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "ts", name="uq_sim_snapshot"),
        Index("ix_sim_snapshots_account_ts", "account_id", "ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    positions_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    def __repr__(self) -> str:
        return f"<SimSnapshot acct={self.account_id} {self.ts} equity={self.equity}>"
