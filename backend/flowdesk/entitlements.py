"""Tier-based entitlements (Phase F5) — what each Keycloak tier may use.

Single source of truth for per-tier resource limits, shared by the custom-agent
and schedule routes. Tiers derive from realm roles (see flowdesk.models.chat_quota).

Note: scheduled agent runs execute on the *platform* provider via run_skill and
do NOT pass through chat-quota enforcement, so free/BYOK tiers get 0 schedules —
this both makes scheduling a paid feature and closes that quota-bypass.
"""

from __future__ import annotations

from flowdesk_core.models.chat_quota import ADMIN_ROLE, BYOK_ROLE

TIER_UNLIMITED = "fd-tier-unlimited"
TIER_2 = "fd-tier-2"
TIER_1 = "fd-tier-1"

# Per-tier caps. Keys are resource names used by the routes.
_LIMITS: dict[str, dict[str, int]] = {
    "admin": {"custom_agents": 100, "schedules": 50, "sim_accounts": 100},
    "unlimited": {"custom_agents": 50, "schedules": 20, "sim_accounts": 50},
    "tier2": {"custom_agents": 20, "schedules": 10, "sim_accounts": 20},
    "tier1": {"custom_agents": 5, "schedules": 3, "sim_accounts": 5},
    "byok": {"custom_agents": 20, "schedules": 0, "sim_accounts": 5},
    "free": {"custom_agents": 2, "schedules": 0, "sim_accounts": 2},
}

# Friendly tier label for the UI.
_LABELS = {
    "admin": "Admin",
    "unlimited": "Unlimited",
    "tier2": "Pro",
    "tier1": "Basic",
    "byok": "BYOK",
    "free": "Free",
}


def roles_from_claims(claims: dict) -> list[str]:
    """Realm roles from a decoded Keycloak JWT claims dict."""
    return claims.get("realm_access", {}).get("roles", [])


def tier_key(roles: list[str]) -> str:
    """Resolve the highest-priority tier from a role list."""
    r = set(roles)
    if ADMIN_ROLE in r:
        return "admin"
    if TIER_UNLIMITED in r:
        return "unlimited"
    if TIER_2 in r:
        return "tier2"
    if TIER_1 in r:
        return "tier1"
    if BYOK_ROLE in r:
        return "byok"
    return "free"


def tier_label(roles: list[str]) -> str:
    return _LABELS[tier_key(roles)]


def limit_for(roles: list[str], resource: str) -> int:
    """Max allowed count of `resource` for this user's tier."""
    return _LIMITS[tier_key(roles)].get(resource, 0)


def all_limits(roles: list[str]) -> dict[str, int]:
    return dict(_LIMITS[tier_key(roles)])
