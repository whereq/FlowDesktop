"""Market Intelligence models: raw news, processed signals, sector aggregates."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class MarketNewsItem(Base):
    """Raw news article or event fetched from an external source.

    Collected by the MarketNewsCollector scheduler job (every 30 min during
    market hours, every 2 h off-hours). Deduplicated by (source, source_id).
    """

    __tablename__ = "market_news_items"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_news_source_id"),
        Index("ix_news_published_at", "published_at"),
        Index("ix_news_is_processed", "is_processed", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # The upstream feed that produced this item
    source_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    region: Mapped[str | None] = mapped_column(String(10))
    # 'US' | 'CN' | 'HK' | 'JP' | 'KR' | 'SG' | 'TW' | 'GLOBAL'
    language: Mapped[str] = mapped_column(String(5), default="en")
    # 'en' | 'zh'
    raw_sentiment: Mapped[float | None] = mapped_column(Float)
    # Provider-supplied sentiment if available (-1.0 to +1.0)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<MarketNewsItem {self.source}:{self.source_id} '{self.title[:40]}'>"


class MarketSignal(Base):
    """AI-processed intelligence signal derived from a MarketNewsItem.

    One signal per news item. Created by the process_market_signals job using
    a structured LLM extraction prompt. Arrays use PostgreSQL native ARRAY type.
    """

    __tablename__ = "market_signals"
    __table_args__ = (
        UniqueConstraint("news_item_id", name="uq_signal_news_item"),
        Index("ix_signal_processed_at", "processed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    news_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # FK to market_news_items.id (not enforced at ORM level for performance)

    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'earnings' | 'macro' | 'geopolitical' | 'sector' | 'regulatory' | 'corporate'

    sentiment: Mapped[float | None] = mapped_column(Float)
    # -1.0 (bearish) to +1.0 (bullish)
    confidence: Mapped[float | None] = mapped_column(Float)
    # 0.0 to 1.0
    impact_horizon: Mapped[str | None] = mapped_column(String(10))
    # 'intraday' | 'short' (1-7d) | 'medium' (1-4w) | 'long'

    regions: Mapped[list[str] | None] = mapped_column(ARRAY(String(10)))
    # e.g. ['US', 'CN']
    sectors_affected: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    # GICS sector names e.g. ['Technology', 'Energy']
    symbols_mentioned: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)))
    # Directly mentioned tickers in Yahoo Finance format
    symbols_impacted: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)))
    # AI-inferred impacted tickers beyond those mentioned
    impact_direction: Mapped[list[str] | None] = mapped_column(ARRAY(String(10)))
    # Parallel to symbols_impacted: 'positive' | 'negative' | 'mixed'
    theme_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    # Short reusable strings e.g. ['US-China trade', 'rate cut', 'AI infrastructure']

    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)

    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_used: Mapped[str | None] = mapped_column(String(50))

    def __repr__(self) -> str:
        return f"<MarketSignal {self.id} type={self.signal_type} sentiment={self.sentiment}>"


class SectorIntelligence(Base):
    """Daily aggregated intelligence for one sector/region pair.

    Built by the build_sector_intelligence job (daily 23:00 UTC).
    Contains AI-generated narrative + weighted sentiment from all signals.
    """

    __tablename__ = "sector_intelligence"
    __table_args__ = (
        UniqueConstraint("sector", "region", "intel_date", name="uq_sector_intel_date"),
        Index("ix_sector_intel_date", "intel_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sector: Mapped[str] = mapped_column(String(50), nullable=False)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    # 'US' | 'CN' | 'HK' | 'GLOBAL' etc.
    intel_date: Mapped[datetime] = mapped_column(Date, nullable=False)

    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float | None] = mapped_column(Float)
    bullish_count: Mapped[int] = mapped_column(Integer, default=0)
    bearish_count: Mapped[int] = mapped_column(Integer, default=0)
    top_themes: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    # Most frequent theme_tags from today's signals

    narrative: Mapped[str | None] = mapped_column(Text)
    # AI-generated 2-3 paragraph sector summary
    key_signal_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    # References to top market_signals.id for this sector/day

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<SectorIntelligence {self.sector}/{self.region} {self.intel_date}>"
