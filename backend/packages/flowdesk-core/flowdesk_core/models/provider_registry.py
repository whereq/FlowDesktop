"""Provider registry — static reference table for all data providers."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ProviderRegistry(Base):
    """Static reference table describing each data provider's capabilities and quotas.

    Seeded once at startup via ProviderOrchestrator.seed_provider_registry().
    Join with crawler_run_log and provider_status to produce the daily stats report.

    Example report query:
        SELECT
            r.run_id, r.job_name, r.provider_name,
            reg.display_name, reg.free_daily_limit,
            ps.daily_used, ps.daily_limit,
            ROUND(ps.daily_used * 100.0 / NULLIF(ps.daily_limit, 0), 1) AS quota_pct,
            r.symbols_attempted, r.symbols_succeeded, r.records_fetched,
            r.duration_seconds, r.status
        FROM crawler_run_log r
        JOIN provider_registry reg ON reg.provider_name = r.provider_name
        JOIN provider_status   ps  ON ps.provider_name  = r.provider_name
        WHERE r.plan_date = CURRENT_DATE
        ORDER BY r.started_at;
    """

    __tablename__ = "provider_registry"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    website_url: Mapped[str | None] = mapped_column(String(255))
    api_endpoint: Mapped[str | None] = mapped_column(String(255))

    # Free-tier quota limits (NULL = unlimited / not applicable)
    free_daily_limit: Mapped[int | None] = mapped_column(Integer)
    free_minute_limit: Mapped[int | None] = mapped_column(Integer)
    free_monthly_limit: Mapped[int | None] = mapped_column(Integer)

    # Supported scope — stored as comma-separated values for easy reading in psql
    supported_exchanges: Mapped[str | None] = mapped_column(String(255))
    # e.g. "NYSE,NASDAQ,TSX,SSE,SZSE"
    supported_data_types: Mapped[str | None] = mapped_column(String(255))
    # e.g. "quote,historical,info"

    # Capability flags
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_realtime: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_historical: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_batch: Mapped[bool] = mapped_column(Boolean, default=False)

    # Human-readable notes (delays, quirks, free-tier restrictions)
    notes: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderRegistry {self.provider_name}"
            f" daily={self.free_daily_limit} min={self.free_minute_limit}>"
        )
