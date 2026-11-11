"""Tier entitlements + current usage for the calling user (Phase F5).

Lets the UI show plan limits, current counts, and gate paid features (e.g.
hide/upsell the Schedule action when schedules are not included).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk.entitlements import all_limits, roles_from_claims, tier_key, tier_label
from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.agent_schedule import AgentSchedule
from flowdesk_core.models.custom_agent import CustomAgent

router = APIRouter(prefix="/me/entitlements", tags=["entitlements"])


@router.get("")
async def get_entitlements(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    uid = UUID(current_user["sub"])
    roles = roles_from_claims(current_user)
    limits = all_limits(roles)

    agents_used = await db.scalar(
        select(func.count()).select_from(CustomAgent).where(CustomAgent.keycloak_id == uid)
    )
    schedules_used = await db.scalar(
        select(func.count()).select_from(AgentSchedule).where(AgentSchedule.keycloak_id == uid)
    )

    return {
        "tier": tier_key(roles),
        "tier_label": tier_label(roles),
        "limits": limits,
        "usage": {
            "custom_agents": agents_used or 0,
            "schedules": schedules_used or 0,
        },
    }
