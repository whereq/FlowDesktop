"""Stock model."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowdesk_core.database import Base


class Stock(Base):
    """Core stock information."""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Chinese name (e.g. 贵州茅台) — populated by sync_chinese_stock_names(); null for non-CN stocks
    name_cn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(50))
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    market_cap: Mapped[int | None] = mapped_column(BigInteger)
    # Multi-exchange expansion columns
    market: Mapped[str] = mapped_column(String(5), default="US")
    currency: Mapped[str] = mapped_column(String(5), default="USD")
    priority_tier: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    quotes: Mapped[list["Quote"]] = relationship(back_populates="stock", lazy="dynamic")
    historical_prices: Mapped[list["HistoricalPrice"]] = relationship(
        back_populates="stock", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Stock {self.symbol}: {self.name}>"


# Import here to avoid circular imports
from flowdesk_core.models.historical import HistoricalPrice  # noqa: E402
from flowdesk_core.models.quote import Quote  # noqa: E402
