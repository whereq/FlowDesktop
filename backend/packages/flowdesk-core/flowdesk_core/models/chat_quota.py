"""Chat quota model — one-time free trial tracking per user."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

# Role constants
ADMIN_ROLE = "fd-admin"
BYOK_ROLE = "fd-tier-byok"  # BYOK-only plan: must use own API key, no FlowDesktop AI
PAID_ROLES = {"fd-tier-1", "fd-tier-2", "fd-tier-unlimited", BYOK_ROLE}

# Free trial limits — when EITHER is hit the trial ends permanently (no reset)
FREE_TRIAL_MESSAGE_LIMIT = 10
FREE_TRIAL_DAYS = 7


class ChatQuota(Base):
    """One-time free trial tracker keyed by Keycloak user UUID.

    The trial starts on the user's first chat message and ends permanently
    when EITHER condition is met first:
      - messages_used >= FREE_TRIAL_MESSAGE_LIMIT (10 messages)
      - now >= trial_start + FREE_TRIAL_DAYS (7 days elapsed)

    There is NO reset. Once exhausted the user must upgrade to a paid tier.
    Paid roles (fd-tier-1, fd-tier-2, fd-tier-unlimited) and fd-admin
    bypass this table entirely.
    """

    __tablename__ = "chat_quotas"

    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    # Fixed start of the one-time 7-day trial window (set on first message)
    trial_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    messages_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ChatQuota {self.keycloak_id} used={self.messages_used}>"
