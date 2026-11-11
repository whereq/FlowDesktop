"""JWT authentication via Keycloak.

FastAPI dependency hierarchy:
  get_current_user  →  verifies Bearer token, returns decoded claims dict
  CurrentUser       →  Annotated type alias — use in route signatures

Usage in a route:
    @router.get("/example")
    async def example(current_user: CurrentUser):
        return {"user": current_user["preferred_username"]}

Public routes (no auth):
    GET /api/v1/health   — Docker health checks must pass without a token
"""

import logging
import os
import time
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration check
# ---------------------------------------------------------------------------

#: The placeholder host from the shipped config. A deployment that still has
#: it has not been configured — it must not look like a real identity provider.
_PLACEHOLDER_URLS = {"", "https://auth.example.com", "http://auth.example.com"}

_NOT_CONFIGURED_DETAIL = (
    "Authentication is not configured. Set KEYCLOAK_URL, KEYCLOAK_REALM and "
    "KEYCLOAK_CLIENT_ID to your OpenID Connect provider before starting "
    "FlowDesktop. See docs/setup.md."
)


def auth_configured() -> bool:
    """True when the identity provider settings are usable.

    False means the deployment still carries the shipped placeholders, so no
    token can be verified and every authenticated route would fail with an
    opaque error.
    """
    settings = get_settings()
    url = (settings.keycloak_url or "").strip().rstrip("/")
    if url.lower() in _PLACEHOLDER_URLS:
        return False
    if not (settings.keycloak_realm or "").strip():
        return False
    return bool((settings.keycloak_client_id or "").strip())


# ---------------------------------------------------------------------------
# JWKS cache — refreshed at most once per hour
# ---------------------------------------------------------------------------
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600.0  # seconds


async def _get_jwks() -> dict:
    """Return cached Keycloak public keys, refreshing when stale."""
    global _jwks_cache, _jwks_fetched_at

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache

    settings = get_settings()

    if not auth_configured():
        logger.error("%s", _NOT_CONFIGURED_DETAIL)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_NOT_CONFIGURED_DETAIL,
        )

    url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
            logger.info("Keycloak JWKS refreshed from %s", url)
    except Exception as exc:
        if _jwks_cache:
            # Serve stale keys rather than taking the API down
            logger.warning("JWKS refresh failed (using cached keys): %s", exc)
        else:
            logger.error("JWKS fetch failed and no cache available: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            )

    return _jwks_cache  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Bearer token extractor
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Verify the Bearer JWT and return its decoded claims.

    Raises 401 for missing/invalid/expired tokens.
    Raises 503 if Keycloak is unreachable and no cached keys exist.
    """
    settings = get_settings()
    token = credentials.credentials
    expected_issuer = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"

    # DEV_BEARER token shortcut for dev/smoke: a raw username passed via
    # `Authorization: Bearer DEV:<username>` synthesizes a user dict without
    # hitting Keycloak. Useful for cron/smoke flows that can't run a real
    # password-grant. NEVER set in prod — would let anyone forge any identity.
    # Hard production gate: this identity-forgery shortcut can NEVER be enabled
    # in prod regardless of the flag (a misconfigured DEV_BEARER=1 in prod was a
    # live auth bypass — 2026-10). Only honored outside ENV=production.
    if (
        token.startswith("DEV:")
        and os.getenv("DEV_BEARER") == "1"
        and os.getenv("ENV", "").lower() != "production"
    ):
        sub = token[4:]
        return {
            "sub": sub,
            "preferred_username": sub,
            "email": f"{sub}@dev.local",
            "_raw_token": token,
        }

    try:
        jwks = await _get_jwks()
        payload: dict = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=expected_issuer,
            options={
                # Audience check: disable here and use azp/client_id instead.
                # Keycloak public-client access tokens do not always include
                # the client ID in `aud`; the `azp` claim is more reliable.
                # To enable strict aud checking, add an Audience mapper in
                # Keycloak: Client Scopes → roles → Mappers → Audience.
                "verify_aud": False,
                "verify_exp": True,
                "verify_iss": True,
            },
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        logger.debug("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate azp (authorized party) — ensures the token was issued for this
    # client, not for another app sharing the same Keycloak realm.
    # DEV_AZP_OVERRIDE accepts additional azp values (comma-separated) so dev/
    # smoke tests using `admin-cli` work without flipping direct-grants on the
    # portal client. Never set in prod — relying on this in production would
    # silently accept tokens minted for arbitrary Keycloak clients.
    azp = payload.get("azp")
    # DEV_AZP_OVERRIDE is also hard-gated off in production.
    extra_azp = (
        os.getenv("DEV_AZP_OVERRIDE", "") if os.getenv("ENV", "").lower() != "production" else ""
    )
    allowed_azp = {
        settings.keycloak_client_id,
        *[x.strip() for x in extra_azp.split(",") if x.strip()],
    }
    if azp not in allowed_azp:
        logger.warning("JWT azp mismatch: expected %r, got %r", settings.keycloak_client_id, azp)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach raw token so downstream handlers can proxy to Keycloak
    payload["_raw_token"] = token
    return payload


# ---------------------------------------------------------------------------
# Convenience type alias — import this in route modules
# ---------------------------------------------------------------------------
CurrentUser = Annotated[dict, Depends(get_current_user)]


async def verify_token(token: str) -> dict | None:
    """Verify a raw JWT string without FastAPI dependency injection.

    Returns the decoded claims dict on success, or None if the token is
    invalid or expired. Used for WebSocket connections where HTTPBearer
    cannot be injected (token is passed as a query parameter instead).
    """
    settings = get_settings()
    expected_issuer = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
    try:
        jwks = await _get_jwks()
        payload: dict = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=expected_issuer,
            options={"verify_aud": False, "verify_exp": True, "verify_iss": True},
        )
        azp = payload.get("azp")
        if azp != settings.keycloak_client_id:
            return None
        payload["_raw_token"] = token
        return payload
    except (ExpiredSignatureError, JWTError):
        return None
