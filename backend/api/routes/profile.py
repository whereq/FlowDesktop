"""User profile endpoints.

GET  /api/v1/me/profile  — FlowDesktop preferences (auto-creates on first access)
PUT  /api/v1/me/profile  — Update FlowDesktop preferences
GET  /api/v1/me/account  — Keycloak account info (proxied)
PUT  /api/v1/me/account  — Update Keycloak account info (proxied)
"""

import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.config import get_settings
from flowdesk_core.database import get_db
from flowdesk_core.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["profile"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ProfileResponse(BaseModel):
    keycloak_id: str
    default_exchange: str | None = None
    default_currency: str | None = None
    timezone: str | None = None
    locale: str | None = None
    bio: str | None = None


class ProfileUpdate(BaseModel):
    default_exchange: str | None = None
    default_currency: str | None = None
    timezone: str | None = None
    locale: str | None = None
    bio: str | None = None


class AccountResponse(BaseModel):
    username: str
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    avatar: str | None = None


class AccountUpdate(BaseModel):
    email: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    avatar: str | None = None


# ---------------------------------------------------------------------------
# FlowDesktop profile (own DB)
# ---------------------------------------------------------------------------
@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's FlowDesktop profile, creating one if needed."""
    uid = UUID(current_user["sub"])
    result = await db.execute(select(UserProfile).where(UserProfile.keycloak_id == uid))
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile(keycloak_id=uid)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return ProfileResponse(
        keycloak_id=str(profile.keycloak_id),
        default_exchange=profile.default_exchange,
        default_currency=profile.default_currency,
        timezone=profile.timezone,
        locale=profile.locale,
        bio=profile.bio,
    )


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's FlowDesktop profile."""
    uid = UUID(current_user["sub"])
    result = await db.execute(select(UserProfile).where(UserProfile.keycloak_id == uid))
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile(keycloak_id=uid)
        db.add(profile)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return ProfileResponse(
        keycloak_id=str(profile.keycloak_id),
        default_exchange=profile.default_exchange,
        default_currency=profile.default_currency,
        timezone=profile.timezone,
        locale=profile.locale,
        bio=profile.bio,
    )


# ---------------------------------------------------------------------------
# Keycloak account (proxied)
# ---------------------------------------------------------------------------
def _account_url() -> str:
    s = get_settings()
    return f"{s.keycloak_url}/realms/{s.keycloak_realm}/account"


@router.get("/account", response_model=AccountResponse)
async def get_account(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return account info from JWT claims + avatar from FlowDesktop DB."""
    username = current_user.get("preferred_username", "")
    email = current_user.get("email")
    first = current_user.get("given_name")
    last = current_user.get("family_name")

    # Avatar is stored in FlowDesktop's own DB (not in Keycloak attributes)
    uid = UUID(current_user["sub"])
    result = await db.execute(select(UserProfile).where(UserProfile.keycloak_id == uid))
    profile = result.scalar_one_or_none()
    avatar = profile.avatar if profile else None

    return AccountResponse(
        username=username,
        email=email,
        firstName=first,
        lastName=last,
        avatar=avatar,
    )


@router.put("/account", response_model=AccountResponse)
async def update_account(
    body: AccountUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Update account: proxy identity fields to Keycloak, save avatar in FlowDesktop DB."""
    raw_token = current_user.get("_raw_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Raw token not available for Keycloak proxy",
        )

    # Proxy identity fields (email, firstName, lastName) to Keycloak.
    # Only include fields that are non-empty strings — sending empty values
    # causes Keycloak to reject the request (e.g. email is required).
    payload: dict = {}
    if body.email:
        payload["email"] = body.email
    if body.firstName:
        payload["firstName"] = body.firstName
    if body.lastName:
        payload["lastName"] = body.lastName

    if payload:
        try:
            url = _account_url()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {raw_token}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code >= 400:
                    # Log but do not fail the whole request — avatar save must still proceed
                    logger.warning(
                        "Keycloak account update failed: %s %s", resp.status_code, resp.text
                    )
        except httpx.HTTPError as exc:
            logger.warning("Keycloak account proxy error (non-fatal): %s", exc)

    # Save avatar in FlowDesktop DB (avoids Keycloak custom-attribute API limitations)
    uid = UUID(current_user["sub"])
    if body.avatar is not None:
        result = await db.execute(select(UserProfile).where(UserProfile.keycloak_id == uid))
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(keycloak_id=uid)
            db.add(profile)
        profile.avatar = body.avatar or None  # empty string → None
        await db.commit()
        await db.refresh(profile)
        saved_avatar = profile.avatar
    else:
        result = await db.execute(select(UserProfile).where(UserProfile.keycloak_id == uid))
        profile = result.scalar_one_or_none()
        saved_avatar = profile.avatar if profile else None

    username = current_user.get("preferred_username", "")
    return AccountResponse(
        username=username,
        email=body.email or current_user.get("email"),
        firstName=body.firstName or current_user.get("given_name"),
        lastName=body.lastName or current_user.get("family_name"),
        avatar=saved_avatar,
    )
