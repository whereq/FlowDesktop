"""PulseTuning — the auto-tuned effective thresholds for NOVA Pulse (singleton).

A single row (id=1) holding the current tuned score_cutoff (and optionally
min_confidence). Written weekly by tune_proactive_thresholds from proactive 👍/👎
feedback; read by the proactive jobs, which fall back to config defaults when a
column is NULL or the row is absent. See docs/design/RFC_NOVA_PROACTIVE_INSIGHTS.md.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class PulseTuning(Base):
    __tablename__ = "pulse_tuning"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1 (singleton)
    score_cutoff: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PulseTuning cutoff={self.score_cutoff} n={self.sample_size} appr={self.approval_rate}>"
