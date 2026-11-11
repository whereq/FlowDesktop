"""Web Push subscription management (owner-scoped).

The browser opts in, hands us a PushSubscription, and we store it. The
notification dispatcher (flowdesk.webpush) sends to every active subscription.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.push_subscription import PushSubscription
from flowdesk_core.webpush import get_application_server_key, is_enabled, send_web_push_to_user

router = APIRouter(prefix="/me/push", tags=["web-push"])


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeIn(BaseModel):
    endpoint: str
    keys: SubKeys


class UnsubscribeIn(BaseModel):
    endpoint: str


@router.get("/key")
async def vapid_public_key(current_user: CurrentUser) -> dict:
    """The applicationServerKey the browser needs to subscribe (null if disabled)."""
    return {"key": get_application_server_key()}


@router.get("")
async def push_status(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    """Whether Web Push is available server-side and whether this user is subscribed."""
    uid = UUID(current_user["sub"])
    count = len(
        (await db.execute(select(PushSubscription.id).where(PushSubscription.keycloak_id == uid)))
        .scalars()
        .all()
    )
    return {"enabled": is_enabled(), "subscribed": count > 0, "devices": count}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    body: SubscribeIn,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register (or refresh) a browser push subscription for this user."""
    uid = UUID(current_user["sub"])
    ua = (request.headers.get("user-agent") or "")[:300]

    existing = await db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    if existing:
        # Same device re-subscribing (possibly a different user/session).
        existing.keycloak_id = uid
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.user_agent = ua
    else:
        db.add(
            PushSubscription(
                keycloak_id=uid,
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
                user_agent=ua,
            )
        )
    await db.commit()
    return {"subscribed": True}


@router.post("/test")
async def send_test_push(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    """Send a test push to all of the caller's subscriptions (verification aid)."""
    uid = UUID(current_user["sub"])
    sent = await send_web_push_to_user(
        db,
        uid,
        {
            "title": "FlowDesktop · NOVA",
            "body": "Push notifications are working. NOVA will reach you here.",
            "data": {"url": "/", "type": "test"},
        },
    )
    await db.commit()  # persist any pruning of dead subscriptions
    return {"sent": sent}


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    body: UnsubscribeIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    """Remove a push subscription (by endpoint) owned by this user."""
    uid = UUID(current_user["sub"])
    sub = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == body.endpoint,
            PushSubscription.keycloak_id == uid,
        )
    )
    if sub:
        await db.delete(sub)
        await db.commit()
