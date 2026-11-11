"""NOVA answer feedback (👍/👎) — owner-writes, admin-reads (eval seeding).

POST stores an eval-ready snapshot. GET (admin only) lists recent feedback so it
can be reviewed and folded into backend/evals. See RFC feedback loop.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.chat_quota import ADMIN_ROLE
from flowdesk_core.models.message_feedback import MessageFeedback

router = APIRouter(prefix="/me/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    rating: int  # +1 or -1
    question: str | None = None
    answer: str | None = None
    agent: str | None = None
    model: str | None = None
    tools_used: list[str] | None = None
    conversation_id: str | None = None


class FeedbackOut(BaseModel):
    id: int
    rating: int
    question: str | None
    answer: str | None
    agent: str | None
    model: str | None
    tools_used: list[str] | None
    created_at: str


def _roles(u: dict) -> list[str]:
    return u.get("realm_access", {}).get("roles", [])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(
    body: FeedbackIn,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    rating = 1 if body.rating > 0 else -1
    conv_uuid = None
    if body.conversation_id:
        try:
            conv_uuid = UUID(str(body.conversation_id))
        except (ValueError, TypeError):
            conv_uuid = None
    db.add(
        MessageFeedback(
            keycloak_id=UUID(current_user["sub"]),
            conversation_id=conv_uuid,
            rating=rating,
            question=(body.question or None),
            answer=(body.answer or None),
            agent=body.agent,
            model=body.model,
            tools_used=body.tools_used or None,
        )
    )
    await db.commit()


@router.get("", response_model=list[FeedbackOut])
async def list_feedback(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    rating: int | None = None,
    limit: int = 100,
):
    """Admin-only: recent feedback for eval review/seeding."""
    if ADMIN_ROLE not in _roles(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    stmt = select(MessageFeedback).order_by(desc(MessageFeedback.id)).limit(max(1, min(limit, 500)))
    if rating is not None:
        stmt = stmt.where(MessageFeedback.rating == (1 if rating > 0 else -1))
    rows = (await db.execute(stmt)).scalars().all()
    return [
        FeedbackOut(
            id=r.id,
            rating=r.rating,
            question=r.question,
            answer=r.answer,
            agent=r.agent,
            model=r.model,
            tools_used=r.tools_used,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
