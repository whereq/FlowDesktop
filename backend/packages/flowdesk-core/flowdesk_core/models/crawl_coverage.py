"""Crawl coverage tracking model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class CrawlCoverage(Base):
    """Track which symbols were successfully collected on which date.

    Enables gap detection and ensures symbols are not silently missed
    due to provider failures or rate-limit exhaustion.
    """

    __tablename__ = "crawl_coverage"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "coverage_date",
            "data_type",
            name="uq_coverage_symbol_date_type",
        ),
        Index("idx_coverage_date_status", "coverage_date", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    coverage_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_type: Mapped[str | None] = mapped_column(String(20))  # 'quote', 'historical', 'info'
    provider: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="success")
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<CrawlCoverage {self.symbol} @ {self.coverage_date}"
            f" [{self.data_type}/{self.provider}] {self.status}>"
        )
