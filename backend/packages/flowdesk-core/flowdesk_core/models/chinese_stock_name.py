"""Chinese stock name reference model.

Source of truth for mapping Chinese stock codes to Chinese-language names.
Populated and iteratively updated by AKShare and TuShare providers.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ChineseStockName(Base):
    """Authoritative Chinese stock name reference table.

    Each row maps a Yahoo Finance symbol (e.g. 600519.SS) to its
    Chinese name (e.g. 贵州茅台).  The table is populated at startup
    and refreshed daily by the sync_chinese_stock_names scheduler job.

    AKShare is the primary source; TuShare fills gaps where AKShare
    has no entry.  ``last_updated_by`` records which provider wrote
    the most recent value so data lineage is traceable.
    """

    __tablename__ = "chinese_stock_names"
    __table_args__ = (
        UniqueConstraint("symbol", name="uq_chinese_stock_names_symbol"),
        Index("idx_chinese_stock_names_symbol", "symbol"),
        Index("idx_chinese_stock_names_code", "code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Full Yahoo Finance symbol — foreign-key-equivalent to stocks.symbol
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    # Bare 6-digit exchange code used by AKShare / TuShare (no suffix)
    code: Mapped[str] = mapped_column(String(10), nullable=False)

    # Chinese name: e.g. 贵州茅台, 五粮液
    name_cn: Mapped[str] = mapped_column(String(100), nullable=False)

    # SSE (Shanghai) or SZSE (Shenzhen)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)

    # 'akshare' or 'tushare' — which provider wrote this row last
    last_updated_by: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<ChineseStockName {self.symbol}: {self.name_cn}>"
