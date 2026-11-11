"""Scheduled agent runs (Phase F4) — "run this agent on a cadence for me".

The collector's dispatcher finds due schedules, runs the referenced agent
headlessly via run_skill, and delivers the brief through the notification
dispatcher (Web Push + in-app). Times are stored in the user's local wall-clock
plus an IANA tz; the dispatcher resolves "is it due now" per timezone.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

CADENCE_DAILY = "daily"
CADENCE_WEEKLY = "weekly"
VALID_CADENCES = {CADENCE_DAILY, CADENCE_WEEKLY}

# Delivery channel codes — values stored in agent_schedules.delivery_channel (text[]).
CHANNEL_IN_APP = "in_app"  # always-on; emit_notification handles this
CHANNEL_EMAIL = "email"  # SES; routes through data_api/scripts/send_newsletter.py
CHANNEL_WEBHOOK = "webhook"  # POST body to schedule.webhook_url
VALID_CHANNELS = {CHANNEL_IN_APP, CHANNEL_EMAIL, CHANNEL_WEBHOOK}


class AgentSchedule(Base):
    """A recurring, unattended run of a NOVA agent for one user."""

    __tablename__ = "agent_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    # Native skill name or a custom-agent slug (resolved via resolve_agent).
    agent_name: Mapped[str] = mapped_column(String(60), nullable=False)
    agent_title: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    symbols: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)), nullable=True)

    cadence: Mapped[str] = mapped_column(String(10), nullable=False, default=CADENCE_DAILY)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Mon..6=Sun (weekly)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)  # local wall-clock
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tz: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # UTC
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ok|empty|error
    # Where to send the brief when it fires. Always include 'in_app' for
    # the in-app inbox + Web Push delivery; add 'email' for SES delivery;
    # add 'webhook' to POST to webhook_url. Stored as a plain comma-joined
    # string so the column stays portable across migrations.
    delivery_channel: Mapped[str] = mapped_column(
        String(64), nullable=False, default=CHANNEL_IN_APP
    )
    # Optional webhook URL — only used when 'webhook' is in delivery_channel.
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<AgentSchedule {self.id} {self.agent_name} {self.cadence} "
            f"{self.hour:02d}:{self.minute:02d} {self.tz} user={self.keycloak_id}>"
        )
