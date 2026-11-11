"""InsiderTransaction — one SEC Form 4 non-derivative transaction.

Populated by the collect_insider_trades job from EDGAR Form 4 ownership documents;
queried by the get_insider_activity tool. One row per transaction line; deduped by
(accession, line_index). See docs/design/RFC_NOVA_INSIDER_ACTIVITY.md.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class InsiderTransaction(Base):
    __tablename__ = "insider_transactions"
    __table_args__ = (
        UniqueConstraint("accession", "line_index", name="uq_insider_txn"),
        # Named after this table. `ix_insider_symbol_date` belongs to the
        # singular `insider_transaction` table (migration 155) — Postgres index
        # names are schema-global, so the two must not share a name.
        Index("ix_insider_transactions_symbol_date", "symbol", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    cik: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accession: Mapped[str] = mapped_column(String(30), nullable=False)
    line_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    insider_name: Mapped[str] = mapped_column(String(150), nullable=False)
    insider_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_director: Mapped[bool] = mapped_column(Boolean, default=False)
    is_officer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ten_pct: Mapped[bool] = mapped_column(Boolean, default=False)

    transaction_code: Mapped[str | None] = mapped_column(String(2), nullable=True)  # P|S|A|M|F|G...
    acquired_disposed: Mapped[str | None] = mapped_column(String(1), nullable=True)  # A|D
    shares: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    shares_owned_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<InsiderTransaction {self.symbol} {self.insider_name} "
            f"{self.transaction_code} {self.shares}@{self.price}>"
        )
