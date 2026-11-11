"""Watchlist model — per-user stock watchlist keyed by Keycloak sub."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class WatchlistItem(Base):
    """A single symbol on a user's watchlist."""

    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("keycloak_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<WatchlistItem {self.keycloak_id} {self.symbol}>"
