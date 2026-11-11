"""User-built custom agent (NOVA Skill stored in the DB) — Phase F1.

A row hydrates into the in-memory `Skill` dataclass and runs through the same
`run_skill` path as native agents, so it inherits every guardrail (tool
subsetting, model tiering, gateway hardening). `tools` is validated against the
ToolRegistry when the agent is created/updated.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class CustomAgent(Base):
    """A user-defined agent. Unique per (owner, name slug)."""

    __tablename__ = "custom_agents"
    __table_args__ = (UniqueConstraint("keycloak_id", "name", name="uq_custom_agent_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(60))  # slug, unique per owner
    title: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40), default="Custom")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    tools: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    model_tier: Mapped[str] = mapped_column(String(10), default="auto")
    temperature: Mapped[float] = mapped_column(Float, default=0.4)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    visibility: Mapped[str] = mapped_column(String(12), default="private")  # private | public
    clone_count: Mapped[int] = mapped_column(Integer, default=0)  # times cloned from community
    icon: Mapped[str] = mapped_column(String(8), default="🤖")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<CustomAgent {self.keycloak_id}:{self.name}>"
