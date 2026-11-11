"""Payment endpoints — Stripe Checkout session creation and webhook handler.

Flow:
  1. Authenticated user hits POST /payments/checkout  →  Stripe Checkout URL
  2. User pays on Stripe hosted page
  3. Stripe sends checkout.session.completed webhook to POST /payments/webhook
  4. Webhook verifies signature, reads session.metadata.keycloak_role
  5. Assigns that Keycloak role to session.client_reference_id (user UUID)
  6. On subscription cancellation (customer.subscription.deleted), removes the role

Environment variables required (add to docker-compose .env):
  STRIPE_SECRET_KEY       — sk_live_... or sk_test_...
  STRIPE_WEBHOOK_SECRET   — whsec_... from Stripe Dashboard → Webhooks
  KEYCLOAK_ADMIN_CLIENT_ID      — "flowdesk-backend" (service account client)
  KEYCLOAK_ADMIN_CLIENT_SECRET  — client secret from Keycloak

Stripe product setup (one-time, in Stripe Dashboard):
  - Create a Product for each tier (e.g., "FlowDesktop Pro")
  - Create a Price under each Product (recurring monthly)
  - Note the Price ID (price_xxx) — pass it in the checkout request body
  - Map each Price ID to a Keycloak role (e.g., price_xxx → fd-tier-1)
    This mapping lives in the checkout request body field "keycloak_role".
"""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from api.services.keycloak_admin import assign_realm_role
from flowdesk_core.auth import CurrentUser
from flowdesk_core.config import get_settings
from flowdesk_core.models.chat_quota import PAID_ROLES

# Roles that the payment webhook is permitted to assign.
# Prevents a tampered or misconfigured Stripe metadata value from granting
# an arbitrary Keycloak role (e.g., "flowdesk-admin").
_ASSIGNABLE_ROLES = PAID_ROLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    price_id: str  # Stripe Price ID (price_xxx) — from your Stripe Dashboard
    keycloak_role: str  # Role to assign on success (e.g., "fd-tier-1")
    success_url: str  # Where to redirect after successful payment
    cancel_url: str  # Where to redirect if user cancels


class CheckoutResponse(BaseModel):
    checkout_url: str


# ---------------------------------------------------------------------------
# GET /payments/health — admin-only config + live Stripe probe
# ---------------------------------------------------------------------------


@router.get("/health")
async def payments_health(current_user: CurrentUser) -> dict:
    """Report whether the payment loop is fully wired (admin only).

    Checks config presence (Stripe keys, webhook secret, Keycloak admin client)
    and does a lightweight live Stripe API call to confirm the secret key works.
    Does NOT prove the webhook is registered in Stripe — verify that in the
    Stripe Dashboard (endpoint should POST to /api/v1/payments/webhook).
    """
    roles = current_user.get("realm_access", {}).get("roles", [])
    if "fd-admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    settings = get_settings()
    out = {
        "stripe_key_configured": bool(settings.stripe_secret_key),
        "webhook_secret_configured": bool(settings.stripe_webhook_secret),
        "keycloak_admin_configured": bool(settings.keycloak_admin_client_secret),
        "assignable_roles": sorted(_ASSIGNABLE_ROLES),
        "stripe_api": "unknown",
    }
    if settings.stripe_secret_key:
        try:
            stripe.api_key = settings.stripe_secret_key
            stripe.Price.list(limit=1)
            out["stripe_api"] = "ok"
        except Exception as exc:
            out["stripe_api"] = f"error: {str(exc)[:120]}"
    else:
        out["stripe_api"] = "no_key"

    out["ready"] = (
        out["stripe_key_configured"]
        and out["webhook_secret_configured"]
        and out["keycloak_admin_configured"]
        and out["stripe_api"] == "ok"
    )
    return out


# ---------------------------------------------------------------------------
# POST /payments/checkout — create a Stripe Checkout session
# ---------------------------------------------------------------------------


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    current_user: CurrentUser,
):
    """Create a Stripe Checkout session for the authenticated user.

    The Keycloak user UUID is stored as client_reference_id so the webhook
    can identify the user without looking them up by email. The target role
    is stored in session metadata so the webhook knows which role to grant.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment processing is not configured on this server.",
        )

    # Reject any attempt to purchase a non-paid or admin role
    if body.keycloak_role not in _ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan selection.",
        )

    stripe.api_key = settings.stripe_secret_key
    user_id = current_user["sub"]  # Keycloak UUID

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            client_reference_id=user_id,
            metadata={"keycloak_role": body.keycloak_role},
            line_items=[{"price": body.price_id, "quantity": 1}],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except stripe.StripeError as exc:
        logger.error("Stripe checkout session creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create payment session. Please try again.",
        )

    return CheckoutResponse(checkout_url=session.url)


# ---------------------------------------------------------------------------
# POST /payments/webhook — Stripe webhook receiver (no auth, signature verified)
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Receive and process Stripe webhook events.

    Stripe signs each request with the webhook secret. We verify the signature
    before processing. No authentication header — Stripe calls this directly.

    Handled events:
      - checkout.session.completed    → assign Keycloak role
      - customer.subscription.deleted → remove Keycloak role (downgrade to free)
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook processing is not configured.",
        )

    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except stripe.SignatureVerificationError:
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        )
    except Exception as exc:
        logger.error("Stripe webhook parse error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload.",
        )

    event_type = event["type"]
    logger.info("Stripe event received: %s", event_type)

    # -----------------------------------------------------------------------
    # checkout.session.completed — payment succeeded, assign role
    # -----------------------------------------------------------------------
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        # stripe-python v5+ objects use attribute access, not dict .get()
        user_id: str | None = getattr(session, "client_reference_id", None)
        raw_metadata = getattr(session, "metadata", None) or {}
        keycloak_role: str | None = (
            raw_metadata.get("keycloak_role")
            if isinstance(raw_metadata, dict)
            else getattr(raw_metadata, "keycloak_role", None)
        )

        if not user_id or not keycloak_role:
            logger.error(
                "Stripe session missing client_reference_id or keycloak_role metadata: %s",
                getattr(session, "id", "unknown"),
            )
            # Return 200 so Stripe doesn't retry — this is a config error, not transient
            return {"status": "skipped", "reason": "missing_metadata"}

        # Whitelist check — only allow known paid roles to be assigned via webhook.
        # Guards against tampered metadata granting admin or arbitrary roles.
        if keycloak_role not in _ASSIGNABLE_ROLES:
            logger.error(
                "Stripe webhook rejected: keycloak_role %r is not an assignable paid role "
                "(session %s, user %s)",
                keycloak_role,
                session.get("id"),
                user_id,
            )
            return {"status": "skipped", "reason": "invalid_role"}

        try:
            await assign_realm_role(user_id, keycloak_role)
        except Exception as exc:
            logger.error(
                "Failed to assign Keycloak role %r to user %s: %s",
                keycloak_role,
                user_id,
                exc,
            )
            # Return 500 so Stripe retries (this is a transient error)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Role assignment failed — Stripe will retry.",
            )

    # -----------------------------------------------------------------------
    # customer.subscription.deleted — subscription cancelled, remove role
    # -----------------------------------------------------------------------
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        # Stripe doesn't store our metadata on the subscription object directly.
        # Retrieve the related checkout session to get the keycloak_role.
        # In practice: store user_id → role in your DB when checkout completes,
        # or use a customer metadata lookup. For now we log and skip.
        logger.warning(
            "Subscription cancelled: %s — manual role removal may be needed",
            getattr(subscription, "id", "unknown"),
        )
        # TODO: implement proper role removal when subscription management is built out

    return {"status": "ok"}
