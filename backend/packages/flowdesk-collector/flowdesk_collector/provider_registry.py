"""Source registry — where this deployment's data comes from.

FlowDesktop has exactly **one** data source: the whereq.cloud Data API, called
with the operator's API key. There is no bundled scraper and no provider
fallback chain, so the registry holds one entry and reports whether the key
is configured.

This module is the public surface for the ``/providers/status`` endpoint. It
reads the ``provider_status`` table, which the collector seeds, so the API
never has to know where the data came from.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("flowdesk-collector.provider-registry")

#: The name the source is recorded under in ``provider_status``.
SOURCE_NAME = "whereq_cloud"

#: The bundled sources. ``requires_key`` documents which ones need a
#: credential to be useful.
BUNDLED_PROVIDERS: list[dict] = [
    {
        "name": SOURCE_NAME,
        "label": "whereq.cloud Data API",
        "requires_key": True,
        "markets": "US, CA, CN, HK, JP, SG, TW, KR, UK, AU, BR, DE, IN",
        "notes": "Market data, history, short interest and insider activity.",
    },
]


def api_key_configured() -> bool:
    """True when a whereq.cloud API key is present in the settings."""
    from flowdesk_core.config import get_settings

    return bool((get_settings().whereq_api_key or "").strip())


async def list_providers(session) -> list[dict]:
    """Return the source status rows recorded by the collector.

    The shape matches ``api.schemas.quote.ProviderStatusResponse``. Falls back
    to the bundled static list when the ``provider_status`` table has not been
    seeded yet (e.g. a brand-new deployment).
    """
    from sqlalchemy import select

    from flowdesk_core.models.provider import ProviderStatus

    try:
        rows = (
            (await session.execute(select(ProviderStatus).order_by(ProviderStatus.priority)))
            .scalars()
            .all()
        )
    except Exception:
        logger.debug("provider_status unreadable — falling back to the bundled list", exc_info=True)
        rows = []

    if not rows:
        return [
            {
                "name": p["name"],
                "priority": priority,
                "daily_limit": None,
                "daily_used": 0,
                "minute_limit": None,
                "minute_used": 0,
                "is_available": api_key_configured(),
                "can_make_request": api_key_configured(),
            }
            for priority, p in enumerate(BUNDLED_PROVIDERS, start=1)
        ]

    return [
        {
            "name": s.provider_name,
            "priority": s.priority,
            "daily_limit": s.daily_limit,
            "daily_used": s.daily_used or 0,
            "minute_limit": s.minute_limit,
            "minute_used": s.minute_used or 0,
            "is_available": s.is_available,
            "can_make_request": s.can_make_request(),
        }
        for s in rows
    ]


async def seed_provider_status(session) -> int:
    """Insert the bundled sources into ``provider_status`` if they are missing.

    Idempotent — safe to call on every collector start.
    """
    from sqlalchemy import select

    from flowdesk_core.models.provider import ProviderStatus

    existing = {
        s.provider_name
        for s in ((await session.execute(select(ProviderStatus.provider_name))).scalars().all())
    }
    added = 0
    for priority, p in enumerate(BUNDLED_PROVIDERS, start=1):
        if p["name"] in existing:
            continue
        session.add(
            ProviderStatus(
                provider_name=p["name"],
                priority=priority,
                daily_limit=None,
                daily_used=0,
                minute_limit=None,
                minute_used=0,
                is_available=api_key_configured(),
            )
        )
        added += 1
    if added:
        await session.commit()
    return added
