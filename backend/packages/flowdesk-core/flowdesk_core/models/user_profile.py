"""User profile model — FlowDesktop-specific preferences keyed by Keycloak sub."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class UserProfile(Base):
    """Per-user preferences stored in FlowDesktop's own database."""

    __tablename__ = "user_profiles"

    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    default_exchange: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_currency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<UserProfile {self.keycloak_id}>"
