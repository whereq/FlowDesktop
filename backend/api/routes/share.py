"""Shareable NOVA analysis snapshots — create + JSON read (auth to create)."""

from __future__ import annotations

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.shared_analysis import SharedAnalysis

router = APIRouter(prefix="/share", tags=["share"])

_MAX_CONTENT = 20000


class ShareIn(BaseModel):
    title: str
    symbol: str | None = None
    content: str


def _public(s: SharedAnalysis) -> dict:
    return {
        "slug": s.slug,
        "title": s.title,
        "symbol": s.symbol,
        "content": s.content,
        "view_count": s.view_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "path": f"/s/{s.slug}",
    }


@router.post("", status_code=201)
async def create_share(
    body: ShareIn, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict:
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "Nothing to share.")
    if len(content) > _MAX_CONTENT:
        content = content[:_MAX_CONTENT]
    title = (body.title or "NOVA analysis").strip()[:200]
    symbol = (body.symbol or "").strip().upper()[:20] or None

    # Unique short slug (retry on the rare collision).
    for _ in range(5):
        slug = secrets.token_urlsafe(8)[:12].replace("_", "a").replace("-", "b")
        exists = await db.scalar(select(SharedAnalysis.id).where(SharedAnalysis.slug == slug))
        if not exists:
            break
    else:
        raise HTTPException(500, "Could not allocate a share link.")

    row = SharedAnalysis(
        slug=slug,
        title=title,
        symbol=symbol,
        content=content,
        created_by=UUID(current_user["sub"]),
    )
    db.add(row)
    await db.commit()
    return _public(row)


@router.get("/{slug}")
async def get_share(slug: str, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.scalar(select(SharedAnalysis).where(SharedAnalysis.slug == slug))
    if not row:
        raise HTTPException(404, "Shared analysis not found.")
    return _public(row)
