"""Historical price model for daily OHLCV data."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowdesk_core.database import Base


class HistoricalPrice(Base):
    """Historical daily price data."""

    __tablename__ = "historical_prices"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_historical_stock_date"),
        Index("idx_historical_stock_date", "stock_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    provider: Mapped[str | None] = mapped_column(String(50))
    # What the provider actually did to the prices.  Providers disagree:
    # some return raw traded prices, some adjust for splits, some also for
    # dividends.  A consumer that stitches two providers' series together
    # needs to know which it is holding.
    #   split_adjusted | split_dividend_adjusted | unadjusted | unknown
    adjustment: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    stock: Mapped["Stock"] = relationship(back_populates="historical_prices")

    def __repr__(self) -> str:
        return f"<HistoricalPrice {self.stock_id} @ {self.date}>"


from flowdesk_core.models.stock import Stock  # noqa: E402
