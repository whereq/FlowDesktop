"""Shadow Portfolio — user's paper trade journal."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ShadowTrade(Base):
    """A single paper trade in a user's shadow portfolio."""

    __tablename__ = "shadow_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(10))  # 'buy' | 'sell'
    shares: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    trade_date: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ShadowTrade {self.keycloak_id} {self.action} {self.shares}x{self.symbol}>"
