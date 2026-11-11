"""Dedup ledger for NOVA Proactive Insights ("NOVA Pulse").

One row per (user, dedup_key) we've already pushed, so the proactive-insights job
is idempotent across collector restarts and collection cycles. The dedup_key is a
*stable* string (e.g. "sig:123" for a market signal, "vol:NVDA:20260628" for a
daily volume/breakout insight) so that one signal touching several of a user's
holdings collapses to a single push, and daily price/volume insights self-dedup by
date. The per-user daily cap is enforced with a COUNT over sent_at >= today.

Mirror of EventReminderSent, generalized. See docs/design/RFC_NOVA_PROACTIVE_INSIGHTS.md.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class ProactiveInsightSent(Base):
    """Marks that a user has been pushed a specific proactive insight."""

    __tablename__ = "proactive_insights_sent"
    __table_args__ = (
        UniqueConstraint("keycloak_id", "dedup_key", name="uq_proactive_insight"),
        Index("ix_proactive_sent_at", "sent_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    # Stable key: "sig:{signal_id}" | "vol:{symbol}:{yyyymmdd}" | "breakout:{symbol}:{yyyymmdd}"
    dedup_key: Mapped[str] = mapped_column(String(80), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # signal | volume | breakout
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ProactiveInsightSent {self.keycloak_id} {self.dedup_key} score={self.score}>"
