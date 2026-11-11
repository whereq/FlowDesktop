"""User-built custom agents (Phase F2) — owner-scoped CRUD.

Custom agents are validated against the ToolRegistry (tools must be a real
subset) and run through the same run_skill path as native agents, so they
inherit all guardrails. Referenced in /chat by their `name` slug.
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.skills import SKILLS
from api.services.tool_registry import ToolRegistry
from flowdesk.entitlements import limit_for, roles_from_claims, tier_label
from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.custom_agent import CustomAgent

router = APIRouter(prefix="/me/agents", tags=["custom-agents"])

_MAX_TOOLS = 10
_MAX_PROMPT = 4000
_TIERS = {"auto", "light", "heavy"}
_VALID_TOOLS = {d["function"]["name"] for d in ToolRegistry().get_definitions()}


class CustomAgentIn(BaseModel):
    name: str
    title: str
    category: str = "Custom"
    description: str | None = None
    system_prompt: str
    tools: list[str] = []
    model_tier: str = "auto"
    temperature: float = 0.4
    max_tokens: int = 1024
    icon: str = "🤖"
    visibility: str = "private"  # private | public (publish to community)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return s[:40]


def _validate(body: CustomAgentIn) -> dict:
    name = _slug(body.name)
    if len(name) < 2:
        raise HTTPException(400, "Name must be at least 2 letters/digits.")
    if name in SKILLS:
        raise HTTPException(400, f"'{name}' is a reserved native agent name.")
    if not body.title.strip():
        raise HTTPException(400, "Title is required.")
    if not body.system_prompt.strip():
        raise HTTPException(400, "Instructions (system prompt) are required.")
    if len(body.system_prompt) > _MAX_PROMPT:
        raise HTTPException(400, f"Instructions too long (max {_MAX_PROMPT} chars).")
    tools = [t for t in (body.tools or []) if t]
    if len(tools) > _MAX_TOOLS:
        raise HTTPException(400, f"Too many tools (max {_MAX_TOOLS}).")
    bad = [t for t in tools if t not in _VALID_TOOLS]
    if bad:
        raise HTTPException(400, f"Unknown tools: {', '.join(bad)}")
    tier = body.model_tier if body.model_tier in _TIERS else "auto"
    return {
        "name": name,
        "title": body.title.strip()[:80],
        "category": (body.category or "Custom").strip()[:40] or "Custom",
        "description": (body.description or "").strip()[:400] or None,
        "system_prompt": body.system_prompt.strip(),
        "tools": tools,
        "model_tier": tier,
        "temperature": max(0.0, min(float(body.temperature), 1.0)),
        "max_tokens": max(128, min(int(body.max_tokens), 2000)),
        "icon": (body.icon or "🤖")[:8],
        "visibility": "public" if body.visibility == "public" else "private",
    }


def _public(a: CustomAgent) -> dict:
    return {
        "name": a.name,
        "title": a.title,
        "category": a.category,
        "description": a.description,
        "tools": list(a.tools or []),
        "model_tier": a.model_tier,
        "example_prompts": [],
        "maturity": "custom",
        "icon": a.icon,
        "custom": True,
        "visibility": a.visibility,
        "clone_count": a.clone_count or 0,
    }


@router.get("")
async def list_my_agents(current_user: CurrentUser, db: AsyncSession = Depends(get_db)) -> dict:
    uid = UUID(current_user["sub"])
    rows = (
        (
            await db.execute(
                select(CustomAgent)
                .where(CustomAgent.keycloak_id == uid)
                .order_by(CustomAgent.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {"count": len(rows), "agents": [_public(a) for a in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_my_agent(
    body: CustomAgentIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    uid = UUID(current_user["sub"])
    fields = _validate(body)
    roles = roles_from_claims(current_user)
    cap = limit_for(roles, "custom_agents")
    count = await db.scalar(
        select(func.count()).select_from(CustomAgent).where(CustomAgent.keycloak_id == uid)
    )
    if count >= cap:
        raise HTTPException(
            402,
            f"You've reached your {tier_label(roles)} plan limit of {cap} custom agents. "
            "Upgrade for more, or delete one first.",
        )
    exists = await db.scalar(
        select(CustomAgent).where(
            CustomAgent.keycloak_id == uid, CustomAgent.name == fields["name"]
        )
    )
    if exists:
        raise HTTPException(409, f"You already have an agent named '{fields['name']}'.")
    agent = CustomAgent(keycloak_id=uid, **fields)
    db.add(agent)
    await db.commit()
    return _public(agent)


class CloneIn(BaseModel):
    source_id: int


@router.post("/clone", status_code=status.HTTP_201_CREATED)
async def clone_agent(
    body: CloneIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    """Clone a public community agent into the caller's own (private) agents.

    Clone-to-run: you copy the agent (and can review/edit its prompt) before it
    runs under your account — so others' prompts never execute on your quota
    unreviewed, which sidesteps the moderation/cost questions for v1.
    """
    uid = UUID(current_user["sub"])
    src = await db.scalar(
        select(CustomAgent).where(
            CustomAgent.id == body.source_id, CustomAgent.visibility == "public"
        )
    )
    if not src:
        raise HTTPException(404, "Public agent not found.")

    roles = roles_from_claims(current_user)
    cap = limit_for(roles, "custom_agents")
    count = await db.scalar(
        select(func.count()).select_from(CustomAgent).where(CustomAgent.keycloak_id == uid)
    )
    if count >= cap:
        raise HTTPException(
            402,
            f"You've reached your {tier_label(roles)} plan limit of {cap} custom agents. "
            "Upgrade for more, or delete one first.",
        )

    # Dedupe the slug within the caller's agents.
    base = src.name[:36]
    name = base
    n = 2
    while await db.scalar(
        select(CustomAgent).where(CustomAgent.keycloak_id == uid, CustomAgent.name == name)
    ):
        name = f"{base}_{n}"
        n += 1

    clone = CustomAgent(
        keycloak_id=uid,
        name=name,
        title=src.title[:80],
        category=src.category,
        description=src.description,
        system_prompt=src.system_prompt,
        tools=list(src.tools or []),
        model_tier=src.model_tier,
        temperature=src.temperature,
        max_tokens=src.max_tokens,
        visibility="private",
        icon=src.icon,
    )
    db.add(clone)
    src.clone_count = (src.clone_count or 0) + 1
    await db.commit()
    return _public(clone)


@router.put("/{name}")
async def update_my_agent(
    name: str, body: CustomAgentIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    uid = UUID(current_user["sub"])
    agent = await db.scalar(
        select(CustomAgent).where(CustomAgent.keycloak_id == uid, CustomAgent.name == name)
    )
    if not agent:
        raise HTTPException(404, "Agent not found.")
    fields = _validate(body)
    fields.pop("name", None)  # name (slug) is immutable once created
    for k, v in fields.items():
        setattr(agent, k, v)
    await db.commit()
    return _public(agent)


class VisibilityIn(BaseModel):
    visibility: str  # private | public


@router.patch("/{name}/visibility")
async def set_visibility(
    name: str, body: VisibilityIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    """Publish (public) or unpublish (private) one of the caller's agents."""
    uid = UUID(current_user["sub"])
    agent = await db.scalar(
        select(CustomAgent).where(CustomAgent.keycloak_id == uid, CustomAgent.name == name)
    )
    if not agent:
        raise HTTPException(404, "Agent not found.")
    agent.visibility = "public" if body.visibility == "public" else "private"
    await db.commit()
    return _public(agent)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_agent(
    name: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    uid = UUID(current_user["sub"])
    agent = await db.scalar(
        select(CustomAgent).where(CustomAgent.keycloak_id == uid, CustomAgent.name == name)
    )
    if not agent:
        raise HTTPException(404, "Agent not found.")
    await db.delete(agent)
    await db.commit()
