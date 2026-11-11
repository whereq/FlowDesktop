"""Web Push subscription model — one browser push endpoint per device.

A user opts in from the browser; the service worker hands us a PushSubscription
(endpoint + p256dh/auth keys) which we store here. The notification dispatcher
(flowdesk.webpush) sends to every active subscription a user has. Having a row
means the user is opted in; deleting it (or a 404/410 from the push service)
means they're out.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class PushSubscription(Base):
    """A single Web Push endpoint for a user's browser/device."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    # The push service URL the browser gave us (unique per device/browser).
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    # Encryption keys from the browser subscription (base64url).
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_subscription_info(self) -> dict:
        """Shape pywebpush expects."""
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }

    def __repr__(self) -> str:
        return f"<PushSubscription {self.id} user={self.keycloak_id}>"
