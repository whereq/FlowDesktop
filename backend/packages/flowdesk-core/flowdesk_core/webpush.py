"""Web Push (VAPID) sender — shared by the API and collector containers.

`send_web_push_to_user` fans a notification out to every browser the user has
opted in from. It's resilient by design: if VAPID isn't configured it's a no-op,
individual send failures never raise, and endpoints the push service reports as
gone (404/410) are pruned so we stop trying them.

Heavy deps (pywebpush, py_vapid) are imported lazily so importing this module is
free where Web Push isn't used.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from functools import lru_cache
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _vapid():
    """Load the VAPID key once. Returns None if not configured."""
    settings = get_settings()
    if not settings.vapid_private_key:
        return None
    try:
        from py_vapid import Vapid02

        pem = base64.b64decode(settings.vapid_private_key)
        return Vapid02.from_pem(pem)
    except Exception as exc:  # malformed key — disable rather than crash
        logger.error("VAPID key load failed; Web Push disabled: %s", exc)
        return None


@lru_cache(maxsize=1)
def get_application_server_key() -> str | None:
    """Public applicationServerKey (base64url) the browser needs to subscribe.

    Derived from the private key, so there's only one secret to manage.
    """
    v = _vapid()
    if v is None:
        return None
    try:
        from cryptography.hazmat.primitives import serialization

        raw = v.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception as exc:
        logger.error("Could not derive applicationServerKey: %s", exc)
        return None


def is_enabled() -> bool:
    return _vapid() is not None


def _send_one(subscription_info: dict, data: str, claims: dict) -> int:
    """Blocking single send. Returns the push service HTTP status (or -1)."""
    from pywebpush import WebPushException, webpush

    try:
        resp = webpush(
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=_vapid(),
            vapid_claims=dict(claims),  # webpush mutates (adds aud/exp)
            ttl=86400,
        )
        return getattr(resp, "status_code", 201)
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", -1)
        if status not in (404, 410):
            logger.warning("Web Push send failed (status=%s): %s", status, exc)
        return status


async def send_web_push_to_user(db: AsyncSession, keycloak_id: UUID, payload: dict) -> int:
    """Send `payload` to all of a user's push subscriptions.

    payload keys: title, body, and optional data (url, type, ...). Returns the
    number of successful sends. Prunes dead (404/410) subscriptions. Never raises.
    """
    v = _vapid()
    if v is None:
        return 0

    from flowdesk_core.models.push_subscription import PushSubscription

    try:
        subs = (
            (
                await db.execute(
                    select(PushSubscription).where(PushSubscription.keycloak_id == keycloak_id)
                )
            )
            .scalars()
            .all()
        )
    except Exception as exc:
        logger.warning("Could not load push subscriptions for %s: %s", keycloak_id, exc)
        return 0

    if not subs:
        return 0

    data = json.dumps(
        {
            "title": payload.get("title", "FlowDesktop"),
            "body": payload.get("body", ""),
            "data": payload.get("data", {}),
        }
    )
    claims = {"sub": get_settings().vapid_subject}

    sent = 0
    dead: list[PushSubscription] = []
    for sub in subs:
        try:
            status = await asyncio.to_thread(_send_one, sub.to_subscription_info(), data, claims)
        except Exception as exc:
            logger.warning("Web Push thread error: %s", exc)
            continue
        if status in (404, 410):
            dead.append(sub)
        elif 200 <= status < 300:
            sent += 1

    if dead:
        for sub in dead:
            await db.delete(sub)
        try:
            await db.flush()
        except Exception:
            pass
        logger.info("Pruned %d dead push subscriptions for %s", len(dead), keycloak_id)

    return sent
