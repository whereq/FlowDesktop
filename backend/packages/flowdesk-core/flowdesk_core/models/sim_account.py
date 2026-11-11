"""SimAccount — a user's virtual paper-trading account, denominated in one currency.

A user may hold several (e.g. one USD, one CNY). An account may only trade stocks
whose currency matches. See docs/design/RFC_STOCK_TRADING_SIMULATOR.md.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class SimAccount(Base):
    __tablename__ = "sim_accounts"
    __table_args__ = (UniqueConstraint("keycloak_id", "name", name="uq_sim_account_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), nullable=False)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<SimAccount {self.id} {self.name} {self.currency} cash={self.cash_balance}>"
