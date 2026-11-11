"""ShortInterest — one short-interest snapshot for a symbol (per settlement date).

Populated by the collect_short_interest job (Yahoo/yfinance); queried by
`GET /v1/alt/short-interest/*` and the get_short_interest tool. One row per
(symbol, settlement_date). See docs/design/RFC_NOVA_ALTDATA_POSITIONING.md.

**Schema note.** This model used to declare the migration-034 column set
(`as_of_date`, `shares_short`, `short_ratio`, `short_pct_float`,
`short_pct_outstanding`, `fetched_at`). Migration 155 created the table
again with the FINRA-shaped column set that the API and the live database
actually use, so every ORM write raised UndefinedColumn and the table stayed
empty. The model below matches the live table; migration 212 adds the
unique constraint the upsert needs and the one Yahoo field that had nowhere
to go (`short_pct_of_outstanding`).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ShortInterest(Base):
    __tablename__ = "short_interest"
    __table_args__ = (
        UniqueConstraint("symbol", "settlement_date", name="uq_short_interest_symbol_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)

    short_interest: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prior_short_interest: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    avg_daily_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    days_to_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_pct_of_float: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_pct_of_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(32), nullable=False, default="Yahoo Finance")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<ShortInterest {self.symbol} {self.settlement_date} "
            f"pctFloat={self.short_pct_of_float}>"
        )
