"""Quote model for real-time stock prices."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flowdesk_core.database import Base


class Quote(Base):
    """Real-time/latest stock quotes."""

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("stock_id", "timestamp", name="uq_quotes_stock_timestamp"),
        Index("idx_quotes_stock_id", "stock_id"),
        Index("idx_quotes_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    change: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    change_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    provider: Mapped[str | None] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    stock: Mapped["Stock"] = relationship(back_populates="quotes")

    def __repr__(self) -> str:
        return f"<Quote {self.stock_id} @ {self.price}>"


from flowdesk_core.models.stock import Stock  # noqa: E402
