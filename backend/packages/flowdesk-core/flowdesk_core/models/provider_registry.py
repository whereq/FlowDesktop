"""Provider registry — static reference table describing each data source."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ProviderRegistry(Base):
    """Static reference table describing each data source's capabilities and quotas.

    FlowDesktop has one data source — the whereq.cloud Data API — so this
    table holds at most one row in practice. It is kept for the schema and for
    anyone who wants to point FlowDesktop at an additional source; the live
    availability of the source itself is tracked in ``provider_status``.
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
