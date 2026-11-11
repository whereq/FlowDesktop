"""MessageFeedback — 👍/👎 on NOVA answers, eval-ready.

Stores a self-contained snapshot (question + answer + agent + tools + model +
rating) so it can seed/score the eval golden set without joining live tables.
See docs/design/RFC_NOVA_MEMORY_CONTINUITY.md (feedback loop).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class MessageFeedback(Base):
    __tablename__ = "message_feedback"
    __table_args__ = (
        Index("ix_feedback_created", "created_at"),
        Index("ix_feedback_rating", "rating"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    keycloak_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # +1 up, -1 down
    question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    agent: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(60))
    tools_used: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
