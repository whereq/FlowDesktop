"""Forward-looking market events — earnings and dividend calendar.

A single table holds both kinds (discriminated by `kind`) so the calendar feed
is one query. Keyed by `symbol` (denormalized, like enrichment) since the bulk
providers return bare tickers. Upserted on (symbol, kind, event_date).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

KIND_EARNINGS = "earnings"
KIND_DIVIDEND = "dividend"
VALID_EVENT_KINDS = {KIND_EARNINGS, KIND_DIVIDEND}


class MarketEvent(Base):
    """One upcoming/recent earnings or dividend event for a symbol."""

    __tablename__ = "market_events"
    __table_args__ = (
        UniqueConstraint("symbol", "kind", "event_date", name="uq_market_event"),
        Index("idx_market_event_date_kind", "event_date", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    # earnings: report date; dividend: ex-dividend date.
    event_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Earnings fields
    time_of_day: Mapped[str | None] = mapped_column(String(4))  # bmo | amc | dmh
    eps_estimate: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    eps_actual: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    revenue_estimate: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    revenue_actual: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    fiscal_period: Mapped[str | None] = mapped_column(String(16))  # e.g. "Q1 2026"

    # Dividend fields
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    currency: Mapped[str | None] = mapped_column(String(8))
    pay_date: Mapped[date | None] = mapped_column(Date)
    record_date: Mapped[date | None] = mapped_column(Date)
    frequency: Mapped[str | None] = mapped_column(String(16))

    provider: Mapped[str] = mapped_column(String(20), default="fmp")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<MarketEvent {self.kind} {self.symbol} {self.event_date}>"
