"""Scheduled agent runs (Phase F4) — owner-scoped CRUD.

A schedule references an agent (native or the caller's custom one), a prompt, a
cadence, and a local time. The collector dispatcher runs due schedules and
delivers the brief via Web Push. Validated against the same resolve_agent path
the chat/runner use, so only runnable agents can be scheduled.
"""

from __future__ import annotations

from uuid import UUID
from zoneinfo import ZoneInfo, available_timezones

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.skills import resolve_agent
from flowdesk.entitlements import limit_for, roles_from_claims, tier_label
from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.agent_schedule import CADENCE_WEEKLY, VALID_CADENCES, AgentSchedule

router = APIRouter(prefix="/me/schedules", tags=["agent-schedules"])

_TZS = available_timezones()


class ScheduleIn(BaseModel):
    agent_name: str
    prompt: str
    symbols: list[str] | None = None
    cadence: str = "daily"
    weekday: int | None = None
    hour: int
    minute: int = 0
    tz: str = "UTC"
    is_active: bool = True


def _public(s: AgentSchedule) -> dict:
    return {
        "id": s.id,
        "agent_name": s.agent_name,
        "agent_title": s.agent_title,
        "prompt": s.prompt,
        "symbols": list(s.symbols or []),
        "cadence": s.cadence,
        "weekday": s.weekday,
        "hour": s.hour,
        "minute": s.minute,
        "tz": s.tz,
        "is_active": s.is_active,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "last_status": s.last_status,
    }


async def _validate(body: ScheduleIn, *, db: AsyncSession, uid: UUID) -> dict:
    if not body.prompt.strip():
        raise HTTPException(400, "Prompt is required.")
    if body.cadence not in VALID_CADENCES:
        raise HTTPException(400, f"Invalid cadence: {body.cadence!r}")
    if body.cadence == CADENCE_WEEKLY and (body.weekday is None or not (0 <= body.weekday <= 6)):
        raise HTTPException(400, "Weekly schedules need a weekday (0=Mon..6=Sun).")
    if not (0 <= body.hour <= 23):
        raise HTTPException(400, "hour must be 0-23.")
    if not (0 <= body.minute <= 59):
        raise HTTPException(400, "minute must be 0-59.")
    tz = body.tz if body.tz in _TZS else "UTC"
    try:
        ZoneInfo(tz)
    except Exception:
        tz = "UTC"

    skill = await resolve_agent(db, str(uid), body.agent_name)
    if skill is None:
        raise HTTPException(400, f"Unknown agent: {body.agent_name!r}")

    symbols = [s.strip().upper() for s in (body.symbols or []) if s.strip()][:10]
    return {
        "agent_name": body.agent_name,
        "agent_title": skill.title[:80],
        "prompt": body.prompt.strip()[:2000],
        "symbols": symbols or None,
        "cadence": body.cadence,
        "weekday": body.weekday if body.cadence == CADENCE_WEEKLY else None,
        "hour": body.hour,
        "minute": body.minute,
        "tz": tz,
        "is_active": body.is_active,
    }


@router.get("")
async def list_schedules(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    uid = UUID(current_user["sub"])
    rows = (
        (
            await db.execute(
                select(AgentSchedule)
                .where(AgentSchedule.keycloak_id == uid)
                .order_by(AgentSchedule.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"count": len(rows), "schedules": [_public(s) for s in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    uid = UUID(current_user["sub"])
    roles = roles_from_claims(current_user)
    cap = limit_for(roles, "schedules")
    if cap <= 0:
        raise HTTPException(
            402,
            "Scheduled agents are a paid feature. Upgrade to Basic or higher to "
            "have NOVA run agents for you automatically.",
        )
    count = await db.scalar(
        select(func.count()).select_from(AgentSchedule).where(AgentSchedule.keycloak_id == uid)
    )
    if count >= cap:
        raise HTTPException(
            402,
            f"You've reached your {tier_label(roles)} plan limit of {cap} scheduled agents. "
            "Upgrade for more, or delete one first.",
        )
    fields = await _validate(body, db=db, uid=uid)
    row = AgentSchedule(keycloak_id=uid, **fields)
    db.add(row)
    await db.commit()
    return _public(row)


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    body: ScheduleIn,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    uid = UUID(current_user["sub"])
    row = await db.scalar(
        select(AgentSchedule).where(
            AgentSchedule.id == schedule_id, AgentSchedule.keycloak_id == uid
        )
    )
    if not row:
        raise HTTPException(404, "Schedule not found.")
    fields = await _validate(body, db=db, uid=uid)
    for k, v in fields.items():
        setattr(row, k, v)
    await db.commit()
    return _public(row)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    uid = UUID(current_user["sub"])
    row = await db.scalar(
        select(AgentSchedule).where(
            AgentSchedule.id == schedule_id, AgentSchedule.keycloak_id == uid
        )
    )
    if not row:
        raise HTTPException(404, "Schedule not found.")
    await db.delete(row)
    await db.commit()
