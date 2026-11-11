"""Investor profile — owner-scoped get / set (M3).

A user-set profile (source='user_set') always wins over the distilled one. NOVA
injects this via ContextBuilder. See docs/design/RFC_NOVA_MEMORY_CONTINUITY.md.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.investor_profile import InvestorProfile

router = APIRouter(prefix="/me/investor-profile", tags=["investor-profile"])


class ProfileIn(BaseModel):
    risk_tolerance: str | None = None
    horizon: str | None = None
    style: str | None = None
    preferred_sectors: list[str] | None = None
    avoided_sectors: list[str] | None = None
    constraints: str | None = None
    goals: str | None = None


class ProfileOut(ProfileIn):
    source: str
    confidence: float | None = None
    updated_at: str | None = None


def _out(p: InvestorProfile | None) -> ProfileOut:
    if p is None:
        return ProfileOut(source="none")
    return ProfileOut(
        risk_tolerance=p.risk_tolerance,
        horizon=p.horizon,
        style=p.style,
        preferred_sectors=p.preferred_sectors,
        avoided_sectors=p.avoided_sectors,
        constraints=p.constraints,
        goals=p.goals,
        source=p.source,
        confidence=p.confidence,
        updated_at=p.updated_at.isoformat() if p.updated_at else None,
    )


@router.get("", response_model=ProfileOut)
async def get_profile(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    p = await db.get(InvestorProfile, UUID(current_user["sub"]))
    return _out(p)


@router.put("", response_model=ProfileOut)
async def set_profile(
    body: ProfileIn,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    uid = UUID(current_user["sub"])
    p = await db.get(InvestorProfile, uid)
    if p is None:
        p = InvestorProfile(keycloak_id=uid)
        db.add(p)
    p.risk_tolerance = body.risk_tolerance
    p.horizon = body.horizon
    p.style = body.style
    p.preferred_sectors = body.preferred_sectors
    p.avoided_sectors = body.avoided_sectors
    p.constraints = body.constraints
    p.goals = body.goals
    p.source = "user_set"  # user-set always wins over distilled
    p.confidence = 1.0
    await db.commit()
    await db.refresh(p)
    return _out(p)
