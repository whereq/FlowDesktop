"""Product jobs — the work that belongs to the application, not the collector.

These run inside the FlowDesktop worker. They depend on the application layer
(``api.services``), which is why they live in the app's own runtime rather than
in a standalone data-collection service.

Three jobs:

* :func:`run_due_agent_schedules` — runs user agent schedules whose local slot
  has arrived, then delivers the brief as a notification.
* :func:`run_sim_order_matcher` — fills resting simulator orders that cross and
  expires day orders.
* :func:`run_sim_snapshots` — daily mark-to-market of every active simulator
  account (the equity curve).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger("flowdesk-collector.product-jobs")


async def run_due_agent_schedules() -> None:
    """Run any agent schedules whose local time has arrived today.

    For each active schedule we resolve "is it due now" in the schedule's own
    timezone, run the agent headlessly via ``run_skill``, and deliver the brief
    through ``emit_notification`` (which fans out to Web Push + in-app).
    """
    from zoneinfo import ZoneInfo

    from sqlalchemy import select

    from flowdesk_core.database import AsyncSessionLocal
    from flowdesk_core.models.agent_schedule import CADENCE_WEEKLY, AgentSchedule

    now_utc = datetime.now(UTC)
    now_utc_naive = now_utc.replace(tzinfo=None)

    async with AsyncSessionLocal() as session:
        schedules = (
            (
                await session.execute(
                    select(AgentSchedule).where(AgentSchedule.is_active == True)  # noqa: E712
                )
            )
            .scalars()
            .all()
        )

        due = []
        for s in schedules:
            try:
                tzinfo = ZoneInfo(s.tz)
            except Exception:
                tzinfo = ZoneInfo("UTC")
            now_local = now_utc.astimezone(tzinfo)
            if (
                s.cadence == CADENCE_WEEKLY
                and s.weekday is not None
                and now_local.weekday() != s.weekday
            ):
                continue
            scheduled_local = now_local.replace(
                hour=s.hour, minute=s.minute, second=0, microsecond=0
            )
            if now_local < scheduled_local:
                continue  # today's slot has not arrived yet
            scheduled_utc_naive = scheduled_local.astimezone(UTC).replace(tzinfo=None)
            if s.last_run_at is not None and s.last_run_at >= scheduled_utc_naive:
                continue  # already ran for this slot
            due.append(s)

        if not due:
            return

        logger.info("Running %d due agent schedule(s)", len(due))
        for s in due:
            try:
                text = await _run_agent_headless(session, s)
                if text:
                    body = text[:600] + ("…" if len(text) > 600 else "")
                    from flowdesk_core.models.user_notification import NOTIF_AGENT_BRIEF
                    from flowdesk_core.notifications import emit_notification

                    await emit_notification(
                        session,
                        s.keycloak_id,
                        NOTIF_AGENT_BRIEF,
                        title=f"{s.agent_title}: scheduled brief",
                        body=body,
                        metadata={
                            "agent": s.agent_name,
                            "schedule_id": s.id,
                            "symbols": s.symbols,
                        },
                    )
                    s.last_status = "ok"
                else:
                    s.last_status = "empty"
            except Exception:
                logger.error("Scheduled agent %s failed", s.id, exc_info=True)
                s.last_status = "error"
            finally:
                s.last_run_at = now_utc_naive

        await session.commit()
    logger.info("Agent schedule run complete")


async def _run_agent_headless(session, s) -> str:
    """Run one agent to completion (non-streaming) and return its full text."""
    from api.services.skills import resolve_agent, run_skill
    from flowdesk_core.llm_platform import strip_thinking

    skill = await resolve_agent(session, str(s.keycloak_id), s.agent_name)
    if skill is None:
        logger.warning("Scheduled agent %s: unknown agent %r", s.id, s.agent_name)
        return ""

    parts: list[str] = []
    async for chunk in run_skill(
        skill,
        db=session,
        user_id=str(s.keycloak_id),
        user_text=s.prompt,
        symbols=s.symbols,
        max_tokens=900,
    ):
        if chunk.get("delta"):
            parts.append(chunk["delta"])
    return strip_thinking("".join(parts)).strip()


async def run_sim_order_matcher() -> None:
    """Fill resting limit/queued orders that cross, and expire day orders."""
    from api.services.simulation import sim_service

    res = await sim_service.match_pending_orders()
    if res["filled"] or res["expired"] or res["rejected"]:
        logger.info(
            "Sim matcher: filled=%d expired=%d rejected=%d",
            res["filled"],
            res["expired"],
            res["rejected"],
        )


async def run_sim_snapshots() -> None:
    """Daily mark-to-market of every active simulator account (equity curve)."""
    from api.services.simulation import sim_service

    n = await sim_service.snapshot_all()
    if n:
        logger.info("Sim snapshots written: %d account(s)", n)
