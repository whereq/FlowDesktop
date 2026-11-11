"""InvestorProfile — structured, durable shape of a user's investing style.

Distilled from conversations (source='distilled') or set by the user
(source='user_set', which always wins). Injected by ContextBuilder so NOVA
grounds answers in the user's risk/horizon/style. Complements the ad-hoc
key-value UserMemory. See docs/design/RFC_NOVA_MEMORY_CONTINUITY.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class InvestorProfile(Base):
    __tablename__ = "investor_profile"

    keycloak_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    risk_tolerance: Mapped[str | None] = mapped_column(
        String(20)
    )  # conservative|moderate|aggressive
    horizon: Mapped[str | None] = mapped_column(String(20))  # day|swing|long_term
    style: Mapped[str | None] = mapped_column(String(30))  # value|growth|income|momentum|mixed
    preferred_sectors: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    avoided_sectors: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    constraints: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)  # distiller confidence 0..1
    source: Mapped[str] = mapped_column(String(20), default="distilled")  # distilled|user_set
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=datetime.utcnow
    )
