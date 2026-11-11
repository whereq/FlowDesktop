"""User memory model — persistent facts NOVA learns across sessions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class UserMemory(Base):
    """A single key-value fact NOVA has learned about a user.

    Written by NOVA's save_memory tool mid-conversation.
    Injected into every new conversation's system prompt by ContextBuilder.
    Upserted on (keycloak_id, memory_key) — one value per key per user.
    """

    __tablename__ = "user_memories"
    __table_args__ = (UniqueConstraint("keycloak_id", "memory_key", name="uq_user_memory_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    memory_key: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<UserMemory {self.keycloak_id} {self.memory_key}={self.memory_value!r}>"
