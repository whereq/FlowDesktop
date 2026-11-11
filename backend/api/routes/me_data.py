"""User memory and notification endpoints.

GET    /api/v1/me/memories              — list all persisted NOVA memories
DELETE /api/v1/me/memories/{key}        — forget a specific memory key

GET    /api/v1/me/notifications         — list recent notifications (unread first)
POST   /api/v1/me/notifications/{id}/read   — mark one notification as read
POST   /api/v1/me/notifications/read-all    — mark all unread as read
WS     /api/v1/me/notifications/ws         — real-time notification stream
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.notification_manager import notification_manager
from flowdesk_core.auth import CurrentUser, verify_token
from flowdesk_core.database import get_db
from flowdesk_core.models.user_memory import UserMemory
from flowdesk_core.models.user_notification import UserNotification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["me"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MemoryItem(BaseModel):
    key: str
    value: str
    updated_at: str


class NotificationItem(BaseModel):
    id: int
    notification_type: str
    title: str
    body: str | None
    metadata: dict | None
    is_read: bool
    created_at: str


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------


@router.get("/memories", response_model=list[MemoryItem])
async def list_memories(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return all NOVA memories for the calling user, newest first."""
    uid = UUID(current_user["sub"])
    result = await db.execute(
        select(UserMemory)
        .where(UserMemory.keycloak_id == uid)
        .order_by(UserMemory.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        MemoryItem(
            key=r.memory_key,
            value=r.memory_value,
            updated_at=r.updated_at.isoformat(),
        )
        for r in rows
    ]


@router.delete("/memories/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    key: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Forget a specific memory key. Silently succeeds if key doesn't exist."""
    uid = UUID(current_user["sub"])
    result = await db.execute(
        select(UserMemory).where(UserMemory.keycloak_id == uid, UserMemory.memory_key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationItem])
async def list_notifications(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
):
    """Return recent notifications for the calling user, unread first."""
    uid = UUID(current_user["sub"])
    stmt = select(UserNotification).where(UserNotification.keycloak_id == uid)
    if unread_only:
        stmt = stmt.where(UserNotification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(UserNotification.is_read.asc(), UserNotification.created_at.desc()).limit(
        limit
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        NotificationItem(
            id=r.id,
            notification_type=r.notification_type,
            title=r.title,
            body=r.body,
            metadata=r.extra_data,
            is_read=r.is_read,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read. Returns 404 if not found or not owned by user."""
    uid = UUID(current_user["sub"])
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.keycloak_id == uid,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    row.is_read = True
    await db.commit()


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Mark all unread notifications as read for the calling user."""
    uid = UUID(current_user["sub"])
    await db.execute(
        update(UserNotification)
        .where(UserNotification.keycloak_id == uid, UserNotification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# WebSocket — real-time notification stream
# ---------------------------------------------------------------------------


@router.websocket("/notifications/ws")
async def notifications_ws(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """Real-time notification stream.

    The client must pass ?token=<JWT> as a query parameter (HTTP headers are
    not reliably sent during WebSocket upgrades in all browsers/frameworks).

    The connection stays open indefinitely. The server pushes JSON payloads
    whenever a new notification arrives for the authenticated user via pg_notify.
    """
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    claims = await verify_token(token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = claims["sub"]
    await notification_manager.connect(websocket, user_id)
    try:
        # Keep alive — listen for client pings or disconnect
        while True:
            data = await websocket.receive_text()
            # Echo pings back so the client can detect connection health
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        notification_manager.disconnect(websocket, user_id)
