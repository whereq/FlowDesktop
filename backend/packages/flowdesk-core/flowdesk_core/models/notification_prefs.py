"""Per-user notification delivery preferences.

Controls which notification categories are pushed to the browser and an optional
quiet-hours window. In-app notifications (the bell/log) are always written; these
prefs only gate the *push* fan-out. One row per user, created lazily with
all-on defaults.
"""

from uuid import UUID

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

# Map a notification_type → the preference attribute that gates its push.
TYPE_TO_PREF = {
    "alert_triggered": "push_alerts",
    "volume_spike": "push_volume",
    "news_signal": "push_signals",
    "sentiment_shift": "push_signals",
    "agent_brief": "push_agent",
    "event_reminder": "push_events",
}


class NotificationPrefs(Base):
    """One user's push delivery preferences."""

    __tablename__ = "notification_prefs"

    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    push_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_volume: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_signals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    push_events: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # When True, proactive insights ("NOVA Pulse") arrive as one daily digest push
    # instead of several individual pushes through the day. Default off.
    proactive_digest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Quiet hours: when enabled, suppress push between [start, end) local time.
    quiet_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiet_start: Mapped[int] = mapped_column(Integer, nullable=False, default=22)  # 0-23 local
    quiet_end: Mapped[int] = mapped_column(Integer, nullable=False, default=7)  # 0-23 local
    tz: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    def allows_push(self, notification_type: str, now_utc) -> bool:
        """Whether a push for this type should be sent right now.

        Default-on semantics: only an explicit False blocks a category. (A
        freshly-constructed, not-yet-persisted instance has None fields because
        SQLAlchemy column defaults apply at insert time, not on instantiation.)
        """
        attr = TYPE_TO_PREF.get(notification_type)
        if attr is not None and getattr(self, attr, None) is False:
            return False
        if self.quiet_enabled:
            try:
                from zoneinfo import ZoneInfo

                hour = now_utc.astimezone(ZoneInfo(self.tz)).hour
            except Exception:
                hour = now_utc.hour
            if _in_quiet_window(hour, self.quiet_start, self.quiet_end):
                return False
        return True


def _in_quiet_window(hour: int, start: int, end: int) -> bool:
    """True if `hour` falls in [start, end), handling overnight wrap (e.g. 22→7)."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # wraps past midnight


# All-on default shape, used by the GET route when the user has no row yet.
DEFAULT_PREFS = {
    "push_alerts": True,
    "push_volume": True,
    "push_signals": True,
    "push_agent": True,
    "push_events": True,
    "proactive_digest": False,
    "quiet_enabled": False,
    "quiet_start": 22,
    "quiet_end": 7,
    "tz": "UTC",
}
