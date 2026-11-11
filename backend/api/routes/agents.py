"""Public catalog of NOVA's native agents (skills), served from the registry.

No auth — this is marketing/discovery metadata (no user data), like /showcase.
The frontend Agents page renders these and deep-links each into NOVA.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.skills import classify_skill, get_skill, list_skills
from api.services.tool_registry import ToolRegistry
from flowdesk_core.database import get_db
from flowdesk_core.models.custom_agent import CustomAgent

router = APIRouter(prefix="/agents", tags=["agents"])

# Tool catalog for the custom-agent builder's tool-picker.
_TOOLS = [
    {"name": d["function"]["name"], "description": d["function"].get("description", "")}
    for d in ToolRegistry().get_definitions()
]


@router.get("")
async def get_agents() -> dict:
    """Return the catalog of native agents and a total count."""
    agents = list_skills()
    return {"count": len(agents), "agents": agents}


@router.get("/tools")
async def get_agent_tools() -> dict:
    """List the data tools a custom agent can be given (for the builder UI)."""
    return {"tools": _TOOLS}


@router.get("/community")
async def community_agents(
    limit: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public, user-published agents — the community catalog (clone-to-run)."""
    rows = (
        (
            await db.execute(
                select(CustomAgent)
                .where(CustomAgent.visibility == "public")
                .order_by(CustomAgent.clone_count.desc(), CustomAgent.updated_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    agents = [
        {
            "id": a.id,
            "title": a.title,
            "category": a.category,
            "description": a.description,
            "tools": list(a.tools or []),
            "model_tier": a.model_tier,
            "icon": a.icon,
            "clone_count": a.clone_count or 0,
        }
        for a in rows
    ]
    return {"count": len(agents), "agents": agents}


@router.get("/suggest")
async def suggest_agent(q: str = "") -> dict:
    """Suggest the best-matching agent for a free-text request (or null).

    A lightweight orchestration aid — the UI can surface "Run with <agent>".
    """
    # Keyword match first (fast, English); fall back to the multilingual local-
    # embedding router for paraphrases / non-English queries it misses.
    name = classify_skill(q)
    if not name and q:
        from api.services.router import route_skill_embedding

        name = await route_skill_embedding(q)
    skill = get_skill(name) if name else None
    return {"query": q, "suggested": skill.public() if skill else None}
