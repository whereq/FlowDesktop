"""Provider status model for rate limit tracking."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ProviderStatus(Base):
    """Track rate limits and availability of data providers."""

    __tablename__ = "provider_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    daily_limit: Mapped[int | None] = mapped_column(Integer)
    daily_used: Mapped[int] = mapped_column(Integer, default=0)
    minute_limit: Mapped[int | None] = mapped_column(Integer)
    minute_used: Mapped[int] = mapped_column(Integer, default=0)
    last_reset: Mapped[datetime | None] = mapped_column(DateTime)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<ProviderStatus {self.provider_name}: {self.daily_used}/{self.daily_limit}>"

    def can_make_request(self) -> bool:
        """Check if provider can handle another request."""
        if not self.is_available:
            return False
        if self.daily_limit and self.daily_used >= self.daily_limit:
            return False
        return not (self.minute_limit and self.minute_used >= self.minute_limit)

    def increment_usage(self) -> None:
        """Increment usage counters."""
        self.daily_used += 1
        self.minute_used += 1
        self.updated_at = datetime.utcnow()
