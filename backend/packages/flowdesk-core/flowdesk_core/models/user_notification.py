"""User notification model — in-app event log."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

# Notification type constants
NOTIF_ALERT_TRIGGERED = "alert_triggered"
NOTIF_VOLUME_SPIKE = "volume_spike"
NOTIF_SENTIMENT_SHIFT = "sentiment_shift"
NOTIF_NEWS_SIGNAL = "news_signal"
NOTIF_AGENT_BRIEF = "agent_brief"
NOTIF_EVENT_REMINDER = "event_reminder"

VALID_NOTIF_TYPES = {
    NOTIF_ALERT_TRIGGERED,
    NOTIF_VOLUME_SPIKE,
    NOTIF_SENTIMENT_SHIFT,
    NOTIF_NEWS_SIGNAL,
    NOTIF_AGENT_BRIEF,
    NOTIF_EVENT_REMINDER,
}


class UserNotification(Base):
    """One in-app notification event for a user.

    Created by collector jobs (alert checks, volume spike detection,
    sentiment shift detection). Delivered in real-time via WebSocket
    (pg_notify → NotificationManager) when the user is online.
    Persisted so offline users see missed events on next login.
    """

    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    # One of VALID_NOTIF_TYPES
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Extra structured data (symbol, price, sector, etc.)
    # Column is named "metadata" in the DB; attribute uses "extra_data" to avoid
    # conflicting with SQLAlchemy's reserved Declarative API attribute.
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return (
            f"<UserNotification {self.id} {self.notification_type} "
            f"user={self.keycloak_id} read={self.is_read}>"
        )
