"""Provider registry — which data sources this deployment can talk to.

FlowDesktop ships with providers that need **no API key**: Yahoo Finance
(quotes + history), Stooq (historical backup), AKShare (China A-shares) and
SEC EDGAR (filings, insider Form 4). Optional key-based providers can be
enabled by setting the matching environment variable; see ``README.md``.

This module is the public surface for the ``/providers/status`` endpoint. It
reads the ``provider_status`` table, which the collector seeds and keeps
updated, so the API never has to know provider internals.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("flowdesk-collector.provider-registry")

#: The providers bundled with FlowDesktop, in fallback order per exchange.
#: ``requires_key`` documents which ones need a credential to be useful.
BUNDLED_PROVIDERS: list[dict] = [
    {
        "name": "yahoo",
        "label": "Yahoo Finance",
        "requires_key": False,
        "markets": "US, CA, JP, SG, TW, KR",
        "notes": "Unofficial API. Unlimited but rate-limited (~100 req/min).",
    },
    {
        "name": "stooq",
        "label": "Stooq",
        "requires_key": False,
        "markets": "US, EU",
        "notes": "Historical only, no real-time.",
    },
    {
        "name": "akshare",
        "label": "AKShare",
        "requires_key": False,
        "markets": "CN (SSE, SZSE)",
        "notes": "Primary source for mainland China listings.",
    },
    {
        "name": "sec_edgar",
        "label": "SEC EDGAR",
        "requires_key": False,
        "markets": "US",
        "notes": "Filings (10-K/10-Q) and insider Form 4 transactions.",
    },
]


async def list_providers(session) -> list[dict]:
    """Return the provider status rows recorded by the collector.

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
                "is_available": True,
                "can_make_request": True,
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
    """Insert the bundled providers into ``provider_status`` if they are missing.

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
                is_available=True,
            )
        )
        added += 1
    if added:
        await session.commit()
    return added
