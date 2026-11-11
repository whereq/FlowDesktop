"""Per-user notification preferences (push categories + quiet hours).

These gate the Web Push fan-out only; in-app notifications are always recorded.
A row is created lazily with all-on defaults the first time the user saves.
"""

from __future__ import annotations

from uuid import UUID
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.notification_prefs import DEFAULT_PREFS, NotificationPrefs

router = APIRouter(prefix="/me/notification-prefs", tags=["notification-prefs"])

_TZS = available_timezones()


class PrefsIn(BaseModel):
    push_alerts: bool = True
    push_volume: bool = True
    push_signals: bool = True
    push_agent: bool = True
    push_events: bool = True
    proactive_digest: bool = False
    quiet_enabled: bool = False
    quiet_start: int = 22
    quiet_end: int = 7
    tz: str = "UTC"


def _public(p: NotificationPrefs) -> dict:
    return {
        "push_alerts": p.push_alerts,
        "push_volume": p.push_volume,
        "push_signals": p.push_signals,
        "push_agent": p.push_agent,
        "push_events": p.push_events,
        "proactive_digest": p.proactive_digest,
        "quiet_enabled": p.quiet_enabled,
        "quiet_start": p.quiet_start,
        "quiet_end": p.quiet_end,
        "tz": p.tz,
    }


@router.get("")
async def get_prefs(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    uid = UUID(current_user["sub"])
    p = await db.scalar(select(NotificationPrefs).where(NotificationPrefs.keycloak_id == uid))
    if p is None:
        return dict(DEFAULT_PREFS)  # all-on default; row created on first save
    return _public(p)


@router.put("")
async def update_prefs(
    body: PrefsIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    uid = UUID(current_user["sub"])
    p = await db.scalar(select(NotificationPrefs).where(NotificationPrefs.keycloak_id == uid))
    if p is None:
        p = NotificationPrefs(keycloak_id=uid)
        db.add(p)

    p.push_alerts = body.push_alerts
    p.push_volume = body.push_volume
    p.push_signals = body.push_signals
    p.push_agent = body.push_agent
    p.push_events = body.push_events
    p.proactive_digest = body.proactive_digest
    p.quiet_enabled = body.quiet_enabled
    p.quiet_start = max(0, min(int(body.quiet_start), 23))
    p.quiet_end = max(0, min(int(body.quiet_end), 23))
    p.tz = body.tz if body.tz in _TZS else "UTC"

    await db.commit()
    return _public(p)
