"""Keycloak Admin REST API client — used for assigning realm roles after payment.

Authentication uses the client credentials flow (service account). The token
is cached in-memory and refreshed automatically when it expires.

Prerequisites (one-time Keycloak setup):
  1. Create a confidential client named "flowdesktop-backend" in your realm.
  2. Enable "Service Accounts Enabled" on that client.
  3. Under "Service Account Roles" assign the "manage-users" realm role.
  4. Copy the client secret into KEYCLOAK_ADMIN_CLIENT_SECRET env var.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)

# In-memory token cache: {"access_token": str, "expires_at": float}
_token_cache: dict[str, Any] = {}


async def _get_admin_token() -> str:
    """Return a valid admin access token, refreshing from Keycloak if needed."""
    settings = get_settings()
    now = time.monotonic()

    if _token_cache.get("access_token") and now < _token_cache.get("expires_at", 0):
        return _token_cache["access_token"]

    token_url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"
    )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.keycloak_admin_client_id,
                "client_secret": settings.keycloak_admin_client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _token_cache["access_token"] = data["access_token"]
    # Subtract 30 s buffer so we refresh before actual expiry
    _token_cache["expires_at"] = now + data.get("expires_in", 60) - 30

    return _token_cache["access_token"]


async def _admin_base_url() -> str:
    settings = get_settings()
    return f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}"


async def get_role_by_name(role_name: str) -> dict:
    """Fetch a realm role object by name (needed for role assignment calls)."""
    token = await _get_admin_token()
    base = await _admin_base_url()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{base}/roles/{role_name}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def assign_realm_role(user_id: str, role_name: str) -> None:
    """Assign a realm role to the user identified by their Keycloak UUID."""
    token = await _get_admin_token()
    base = await _admin_base_url()
    role = await get_role_by_name(role_name)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{base}/users/{user_id}/role-mappings/realm",
            headers={"Authorization": f"Bearer {token}"},
            json=[role],
        )
        resp.raise_for_status()
    logger.info("Assigned role %r to user %s", role_name, user_id)


async def remove_realm_role(user_id: str, role_name: str) -> None:
    """Remove a realm role from the user (e.g., on subscription cancellation)."""
    token = await _get_admin_token()
    base = await _admin_base_url()
    role = await get_role_by_name(role_name)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(
            f"{base}/users/{user_id}/role-mappings/realm",
            headers={"Authorization": f"Bearer {token}"},
            json=[role],
        )
        resp.raise_for_status()
    logger.info("Removed role %r from user %s", role_name, user_id)
