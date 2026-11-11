"""User price alert endpoints.

GET    /api/v1/me/alerts              — list all alerts for the current user
POST   /api/v1/me/alerts              — create an alert
DELETE /api/v1/me/alerts/{id}         — delete an alert
PATCH  /api/v1/me/alerts/{id}/rearm   — re-enable a triggered alert
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.user_alert import VALID_ALERT_TYPES, UserAlert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class AlertResponse(BaseModel):
    id: int
    symbol: str
    alert_type: str
    threshold: float
    is_active: bool
    triggered_at: datetime | None
    created_at: datetime


class AlertCreateRequest(BaseModel):
    symbol: str
    alert_type: str
    threshold: float

    @field_validator("alert_type")
    @classmethod
    def validate_alert_type(cls, v: str) -> str:
        if v not in VALID_ALERT_TYPES:
            raise ValueError(f"alert_type must be one of: {sorted(VALID_ALERT_TYPES)}")
        return v

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper().strip()
        if not v:
            raise ValueError("symbol is required")
        return v


def _uid(current_user: dict) -> UUID:
    return UUID(current_user["sub"])


def _to_response(alert: UserAlert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        symbol=alert.symbol,
        alert_type=alert.alert_type,
        threshold=alert.threshold,
        is_active=alert.is_active,
        triggered_at=alert.triggered_at,
        created_at=alert.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return all alerts for the current user, newest first."""
    uid = _uid(current_user)
    result = await db.execute(
        select(UserAlert).where(UserAlert.keycloak_id == uid).order_by(UserAlert.created_at.desc())
    )
    return [_to_response(a) for a in result.scalars().all()]


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AlertCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Create a price alert. Duplicate (symbol, alert_type) replaces the old threshold."""
    uid = _uid(current_user)

    # Upsert: if the same (user, symbol, alert_type) exists, update threshold + re-arm
    existing = await db.execute(
        select(UserAlert).where(
            UserAlert.keycloak_id == uid,
            UserAlert.symbol == body.symbol,
            UserAlert.alert_type == body.alert_type,
        )
    )
    alert = existing.scalar_one_or_none()

    if alert is not None:
        alert.threshold = body.threshold
        alert.is_active = True
        alert.triggered_at = None
    else:
        alert = UserAlert(
            keycloak_id=uid,
            symbol=body.symbol,
            alert_type=body.alert_type,
            threshold=body.threshold,
            is_active=True,
        )
        db.add(alert)

    await db.commit()
    await db.refresh(alert)
    return _to_response(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert. No-op if it doesn't exist or belongs to another user."""
    uid = _uid(current_user)
    await db.execute(
        delete(UserAlert).where(
            UserAlert.id == alert_id,
            UserAlert.keycloak_id == uid,
        )
    )
    await db.commit()


@router.patch("/{alert_id}/rearm", response_model=AlertResponse)
async def rearm_alert(
    alert_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Re-enable a triggered alert so it can fire again."""
    uid = _uid(current_user)
    result = await db.execute(
        select(UserAlert).where(
            UserAlert.id == alert_id,
            UserAlert.keycloak_id == uid,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_active = True
    alert.triggered_at = None
    await db.commit()
    await db.refresh(alert)
    return _to_response(alert)
