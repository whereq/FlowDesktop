"""CompanyFiling — source-of-truth for SEC filing narrative (10-K / 10-Q).

One row per fetched filing primary document. The collect_filings job upserts these
(deduped by accession); the embedding indexer chunks `content` into retrieval_chunks
(source_type='filing', source_id=CompanyFiling.id) for NOVA's search_filings tool.
See docs/design/RFC_NOVA_FILINGS_GROUNDING.md.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class CompanyFiling(Base):
    __tablename__ = "company_filings"
    __table_args__ = (
        UniqueConstraint("accession", name="uq_filing_accession"),
        Index("ix_filing_symbol_form", "symbol", "form"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cik: Mapped[int] = mapped_column(BigInteger, nullable=False)
    form: Mapped[str] = mapped_column(String(12), nullable=False)  # 10-K | 10-Q
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    accession: Mapped[str] = mapped_column(String(30), nullable=False)  # globally unique per SEC
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CompanyFiling {self.symbol} {self.form} {self.filing_date} {self.accession}>"
