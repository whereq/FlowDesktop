"""Shared notification helper — used by both collector and API containers.

Writes a UserNotification row and fires pg_notify on channel
"user_notifications" so the API's WebSocket listener can deliver it in
real-time to connected clients.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.models.user_notification import VALID_NOTIF_TYPES, UserNotification

logger = logging.getLogger(__name__)


def _json_safe(v):
    """Recursively coerce a value into something JSON/JSONB-serializable.

    NUMERIC columns surface as Decimal, which asyncpg cannot encode into a JSONB
    param — an unsanitized metadata dict poisons the session's flush and takes
    the whole job down with it. Convert Decimal→float, datetimes→isoformat."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    return v


async def _push_allowed(db: AsyncSession, keycloak_id: UUID, notification_type: str) -> bool:
    """Consult the user's notification prefs for whether to push this type now.

    Missing prefs row = all-on default. Failures default to allow (best-effort).
    """
    from datetime import datetime

    from sqlalchemy import select

    from flowdesk_core.models.notification_prefs import NotificationPrefs

    try:
        prefs = await db.scalar(
            select(NotificationPrefs).where(NotificationPrefs.keycloak_id == keycloak_id)
        )
    except Exception:
        return True
    if prefs is None:
        return True
    return prefs.allows_push(notification_type, datetime.now(UTC))


async def emit_notification(
    db: AsyncSession,
    keycloak_id: UUID,
    notification_type: str,
    title: str,
    body: str | None = None,
    metadata: dict | None = None,
) -> UserNotification:
    """Write a UserNotification row and fire pg_notify.

    Channel: "user_notifications"
    Payload: JSON with id, keycloak_id, notification_type, title, body,
             metadata, is_read, created_at.

    Caller is responsible for committing the session if they want the row
    persisted. This function calls flush() to populate notif.id but does
    NOT commit — batch callers can commit once after multiple emits.
    """
    if notification_type not in VALID_NOTIF_TYPES:
        raise ValueError(f"Invalid notification_type: {notification_type!r}")

    metadata = _json_safe(metadata) if metadata is not None else None

    notif = UserNotification(
        keycloak_id=keycloak_id,
        notification_type=notification_type,
        title=title,
        body=body,
        extra_data=metadata,
        is_read=False,
    )
    db.add(notif)
    await db.flush()  # populate notif.id

    payload = json.dumps(
        {
            "id": notif.id,
            "keycloak_id": str(keycloak_id),
            "notification_type": notification_type,
            "title": title,
            "body": body,
            "metadata": metadata,
            "is_read": False,
            "created_at": notif.created_at.isoformat() if notif.created_at else None,
        }
    )
    await db.execute(
        sqlalchemy.text("SELECT pg_notify('user_notifications', :payload)"),
        {"payload": payload},
    )

    # Web Push fan-out: reach the user even when no tab is open. Gated by the
    # user's notification preferences (per-type toggle + quiet hours). No-op if
    # VAPID isn't configured or the user has no subscriptions; never fatal.
    try:
        if await _push_allowed(db, keycloak_id, notification_type):
            from flowdesk_core.webpush import send_web_push_to_user

            md = metadata or {}
            symbol = md.get("symbol")
            # Callers may override the click target (e.g. proactive insights open
            # NOVA pre-seeded via /?ask=...). Default: the stock page.
            url = md.get("url") or (f"/stock/{symbol}" if symbol else "/")
            await send_web_push_to_user(
                db,
                keycloak_id,
                {
                    "title": title,
                    "body": body or "",
                    "data": {"url": url, "type": notification_type, "id": notif.id},
                },
            )
    except Exception as exc:  # delivery must never break the notification write
        logger.warning("Web Push dispatch error (user=%s): %s", keycloak_id, exc)

    logger.debug(
        "emit_notification: user=%s type=%s title=%r",
        keycloak_id,
        notification_type,
        title,
    )
    return notif
