"""Chat endpoints — streaming LLM conversation, provider listing, and quota."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_gateway import (
    LLMError,
    LLMGateway,
    build_provider_list,
    provider_api_base,
    resolve_api_key,
    resolve_platform_provider,
    validate_provider_key,
)
from api.services.skills import resolve_agent
from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.chat_quota import (
    ADMIN_ROLE,
    BYOK_ROLE,
    FREE_TRIAL_DAYS,
    FREE_TRIAL_MESSAGE_LIMIT,
    PAID_ROLES,
    ChatQuota,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MessagePayload(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    provider: str
    model: str
    mode: str = "platform"
    messages: list[MessagePayload]
    symbols: list[str] | None = None
    locale: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    # Optional skill/agent to run this turn as (scoped tools + persona + tier).
    # None = the generalist NOVA chat (unchanged default).
    agent: str | None = None
    # Optional conversation to persist into / resume (server-side memory).
    # None = stateless (legacy behavior); the server may create one and return it.
    conversation_id: str | None = None
    # When True, let the router auto-run a confidently-matched agent if none chosen.
    auto_dispatch: bool = True


class ProviderModel(BaseModel):
    id: str
    label: str


class ProviderInfo(BaseModel):
    name: str
    models: list[ProviderModel]
    platform_available: bool


class QuotaResponse(BaseModel):
    """Current quota state for the calling user.

    tier:              "admin" | "paid" | "free"
    limit:             message cap for the trial (None = unlimited)
    used:              messages sent so far in the trial
    trial_start:       when the trial started (None = unlimited)
    trial_end:         when the trial expires (None = unlimited)
    trial_exhausted:   True when either message limit OR time limit is hit
    exhausted_reason:  "messages" | "time" | None
    days_remaining:    days left in trial window (0 if exhausted, None if unlimited)
    """

    tier: str
    limit: int | None
    used: int
    trial_start: datetime | None
    trial_end: datetime | None
    trial_exhausted: bool
    exhausted_reason: str | None
    days_remaining: int | None


# ---------------------------------------------------------------------------
# Quota helpers
# ---------------------------------------------------------------------------


def _extract_roles(current_user: dict) -> list[str]:
    """Extract realm roles from the decoded Keycloak JWT claims."""
    return current_user.get("realm_access", {}).get("roles", [])


def _user_tier(roles: list[str]) -> str:
    """Derive access tier from role list. Checked in priority order."""
    if ADMIN_ROLE in roles:
        return "admin"
    if PAID_ROLES & set(roles):
        return "paid"
    return "free"


async def _resolve_quota(
    db: AsyncSession,
    user_id: UUID,
    roles: list[str],
    *,
    increment: bool = False,
) -> QuotaResponse:
    """Return the user's current quota state.

    When increment=True, consume one trial message before returning.
    Raises HTTP 429 if the free trial is exhausted (messages or time).
    Admin and paid roles always return unlimited state without touching the DB.
    """
    tier = _user_tier(roles)

    # Admin and paid tiers: unlimited, no DB interaction
    if tier in ("admin", "paid"):
        return QuotaResponse(
            tier=tier,
            limit=None,
            used=0,
            trial_start=None,
            trial_end=None,
            trial_exhausted=False,
            exhausted_reason=None,
            days_remaining=None,
        )

    # Free tier — check or initialize trial row.
    # Use SELECT FOR UPDATE to serialize concurrent requests for the same user,
    # preventing race conditions where two simultaneous requests both pass
    # the quota check before either increments the counter.
    now = datetime.utcnow()
    result = await db.execute(
        select(ChatQuota).where(ChatQuota.keycloak_id == user_id).with_for_update()
    )
    quota = result.scalar_one_or_none()
    dirty = False

    if quota is None:
        quota = ChatQuota(
            keycloak_id=user_id,
            trial_start=now,
            messages_used=0,
        )
        db.add(quota)
        dirty = True

    trial_end = quota.trial_start + timedelta(days=FREE_TRIAL_DAYS)
    time_exhausted = now >= trial_end
    messages_exhausted = quota.messages_used >= FREE_TRIAL_MESSAGE_LIMIT
    trial_exhausted = time_exhausted or messages_exhausted
    exhausted_reason = "time" if time_exhausted else "messages" if messages_exhausted else None
    days_remaining = max(0, (trial_end - now).days) if not trial_exhausted else 0

    if increment:
        if trial_exhausted:
            if dirty:
                await db.commit()
            reason_msg = (
                "Your 7-day free trial has expired."
                if time_exhausted
                else f"Free trial message limit reached ({FREE_TRIAL_MESSAGE_LIMIT} messages)."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{reason_msg} Upgrade to continue.",
            )
        quota.messages_used += 1
        dirty = True

    if dirty:
        await db.commit()

    return QuotaResponse(
        tier="free",
        limit=FREE_TRIAL_MESSAGE_LIMIT,
        used=quota.messages_used,
        trial_start=quota.trial_start,
        trial_end=trial_end,
        trial_exhausted=trial_exhausted,
        exhausted_reason=exhausted_reason,
        days_remaining=days_remaining,
    )


# ---------------------------------------------------------------------------
# GET /chat/quota — current user's quota state (read-only, no increment)
# ---------------------------------------------------------------------------


@router.get("/quota", response_model=QuotaResponse)
async def get_quota(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return the calling user's current chat quota status.

    Safe to call repeatedly — never consumes quota.
    Admin and paid-tier users receive tier='admin'/'paid' with no limits.
    """
    roles = _extract_roles(current_user)
    return await _resolve_quota(db, UUID(current_user["sub"]), roles)


# ---------------------------------------------------------------------------
# POST /chat — streaming chat
# ---------------------------------------------------------------------------


@router.post("")
async def chat(
    request: ChatRequest,
    current_user: CurrentUser,
    x_llm_api_key: str | None = Header(None, alias="X-LLM-Api-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Streaming chat endpoint. Auth required. BYOK key via X-LLM-Api-Key header.

    Quota applies to platform mode only — BYOK users provide their own API key
    so there is no server cost. Admin and paid roles are always unlimited.
    Free trial ends permanently once 10 messages OR 7 days are consumed.
    """
    # Resolve provider + key based on mode.
    # Platform mode: backend picks the first configured provider from .env —
    #   the frontend's provider claim is intentionally ignored.
    # BYOK mode: frontend specifies provider; user supplies their own API key.
    if request.mode == "platform":
        try:
            provider_name, model, api_key = resolve_platform_provider()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
        platform_api_base = provider_api_base(provider_name)
        roles = _extract_roles(current_user)
        # BYOK-only plan users cannot use FlowDesktop AI — they must supply their own key
        if BYOK_ROLE in roles and ADMIN_ROLE not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your BYOK plan does not include FlowDesktop AI. "
                    "Configure a provider in Settings → AI Assistant → Use My Own Key."
                ),
            )
        # Quota enforcement — platform mode only, raises 429 if trial exhausted
        await _resolve_quota(db, UUID(current_user["sub"]), roles, increment=True)
    else:
        provider_name = request.provider
        model = request.model
        platform_api_base = None  # BYOK: customer manages their own endpoint
        try:
            api_key = resolve_api_key(request.mode, provider_name, x_llm_api_key)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    gateway = LLMGateway()
    user_id = current_user.get("sub")
    last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")

    # If an agent (skill) was selected, scope this turn to it: curated tools,
    # focused persona prompt, and pinned model tier. Resolves native agents and
    # the caller's own custom agents. Unknown agent → ignored (generalist chat).
    skill = await resolve_agent(db, user_id, request.agent) if request.agent else None

    # Auto-dispatch: when no agent was chosen, let the (multilingual) router pick a
    # confidently-matched skill and run this turn as it. Platform mode only.
    auto_agent: str | None = None
    if not skill and request.mode == "platform" and request.auto_dispatch and last_user:
        from api.services.router import route_skill_embedding
        from api.services.skills import classify_skill

        name = classify_skill(last_user) or await route_skill_embedding(last_user)
        if name:
            resolved = await resolve_agent(db, user_id, name)
            if resolved:
                skill = resolved
                auto_agent = name

    # Conversation persistence (opt-in via conversation_id; server may create one).
    # Best-effort — failures degrade to stateless, never block the chat.
    from api.services.conversation_store import get_or_create, persist_turn

    conv = await get_or_create(
        db,
        user_id,
        request.conversation_id,
        agent=(skill.name if skill else None),
        symbols=request.symbols,
        first_text=last_user,
    )
    conv_id = str(conv.id) if conv else None
    history_summary = conv.rolling_summary if conv else None
    is_new_conv = bool(conv and not request.conversation_id)

    async def event_stream():
        assistant_parts: list[str] = []
        tools_used_acc: list[str] = []
        try:
            if is_new_conv and conv_id:
                yield f"data: {json.dumps({'type': 'conversation', 'id': conv_id})}\n\n"
            if auto_agent and skill:
                yield f"data: {json.dumps({'type': 'agent_auto', 'name': auto_agent, 'title': skill.title})}\n\n"
            async for chunk in gateway.stream_chat(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                messages=[m.model_dump() for m in request.messages],
                db=db,
                user_id=user_id,
                symbols=request.symbols,
                locale=request.locale,
                temperature=skill.temperature if skill else request.temperature,
                max_tokens=request.max_tokens,
                api_base=platform_api_base,
                allow_routing=(request.mode == "platform"),
                tool_names=list(skill.tools) if skill else None,
                system_suffix=skill.system_prompt if skill else None,
                force_tier=skill.model_tier if skill else None,
                history_summary=history_summary,
            ):
                if isinstance(chunk, dict):
                    if chunk.get("delta"):
                        assistant_parts.append(chunk["delta"])
                    elif chunk.get("type") == "tools_used":
                        tools_used_acc = chunk.get("tools", [])
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except LLMError as exc:
            logger.error("Chat LLM error [%s]: %s", exc.code, exc)
            yield f"data: {json.dumps({'error_code': exc.code, 'error': str(exc)})}\n\n"
        except Exception as exc:
            logger.error("Chat error: %s", exc)
            yield f"data: {json.dumps({'error_code': 'transient', 'error': str(exc)[:300]})}\n\n"
        finally:
            # Persist the turn (best-effort, isolated session).
            if conv_id:
                answer = "".join(assistant_parts).strip()
                if answer:
                    try:
                        await persist_turn(
                            conversation_id=conv_id,
                            user_text=last_user,
                            assistant_text=answer,
                            tools_used=tools_used_acc,
                            agent=(skill.name if skill else None),
                            symbols=request.symbols,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("persist_turn error: %s", exc)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# GET /chat/providers — list providers + models
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(current_user: CurrentUser):
    """Return available LLM providers and their models. Auth required."""
    return build_provider_list()


# ---------------------------------------------------------------------------
# POST /chat/validate-key — verify a BYOK API key with a 1-token ping
# ---------------------------------------------------------------------------


class ValidateKeyRequest(BaseModel):
    provider: str
    api_key: str


class ValidateKeyResponse(BaseModel):
    # True=valid, False=invalid, None=inconclusive (connection error)
    valid: bool | None
    # Machine-readable code; frontend maps this to a localised string.
    # Never contains raw exception text.
    message_code: str


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_key(
    request: ValidateKeyRequest,
    current_user: CurrentUser,
):
    """Validate a user-supplied BYOK API key by making a minimal 1-token completion.

    Returns valid=True even on RateLimitError — the key is authentic, just quota-limited.
    Returns valid=None on connection errors — key validity cannot be determined.
    Never charges quota to the FlowDesktop platform account.
    """
    valid, message_code = await validate_provider_key(request.provider, request.api_key)
    return ValidateKeyResponse(valid=valid, message_code=message_code)
