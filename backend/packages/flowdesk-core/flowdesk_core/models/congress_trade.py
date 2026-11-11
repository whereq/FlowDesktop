"""CongressTrade — one US congressional stock transaction (STOCK Act disclosure).

Sourced from the community senate/house-stock-watcher datasets by the
collect_congress_trades job; queried by the get_congress_trades tool. Third-party
disclosure data (best-effort). Deduped by a stable hash. See
docs/design/RFC_NOVA_ALTDATA_POSITIONING.md.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class CongressTrade(Base):
    __tablename__ = "congress_trades"
    __table_args__ = (
        UniqueConstraint("dedup_hash", name="uq_congress_trade_hash"),
        Index("ix_congress_symbol_date", "symbol", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chamber: Mapped[str] = mapped_column(String(8), nullable=False)  # senate | house
    politician: Mapped[str] = mapped_column(String(150), nullable=False)
    party: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disclosure_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    txn_type: Mapped[str | None] = mapped_column(String(12), nullable=True)  # buy | sell | exchange
    amount_range: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CongressTrade {self.symbol} {self.politician} {self.txn_type} {self.transaction_date}>"
