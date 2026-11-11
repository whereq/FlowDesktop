"""Enrichment data models: fundamental financial data and macro indicators."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class FundamentalDataRecord(Base):
    """Fundamental financial data sourced from SEC EDGAR XBRL filings.

    Each record corresponds to one XBRL concept (e.g. Revenues, NetIncomeLoss)
    for one filing period and one stock.
    """

    __tablename__ = "fundamental_data"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "concept",
            "period_end",
            "form",
            name="uq_fundamental_symbol_concept_period_form",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cik: Mapped[str | None] = mapped_column(String(10))
    concept: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str | None] = mapped_column(String(50))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    form: Mapped[str | None] = mapped_column(String(20))  # 10-K, 10-Q
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)  # 1-4, None for annual
    provider: Mapped[str] = mapped_column(String(20), default="sec_edgar")
    filed_date: Mapped[date | None] = mapped_column(
        Date, index=True
    )  # point-in-time: when filed/public
    accession: Mapped[str | None] = mapped_column(String(24))  # SEC accession of source filing
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<FundamentalDataRecord {self.symbol} {self.concept} {self.period_end} ({self.form})>"
        )


class MacroIndicatorRecord(Base):
    """Macroeconomic indicator record sourced from FRED.

    Each record is one observation of a FRED economic series (e.g. FEDFUNDS)
    on a specific date.
    """

    __tablename__ = "macro_indicators"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "indicator_date",
            name="uq_macro_series_date",
        ),
        Index("idx_macro_series_date", "series_id", "indicator_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    series_name: Mapped[str | None] = mapped_column(String(100))
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    indicator_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20), default="fred")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<MacroIndicatorRecord {self.series_id} @ {self.indicator_date} = {self.value}>"
