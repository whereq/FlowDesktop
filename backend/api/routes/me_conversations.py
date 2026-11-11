"""Conversation history — owner-scoped list / get / rename / delete (M1).

Server-side persistence written by POST /chat (conversation_store). See
docs/design/RFC_NOVA_MEMORY_CONTINUITY.md.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.embeddings import (
    EmbeddingError,
    embed_query,
    embedding_model_id,
)
from flowdesk_core.embeddings import (
    is_configured as embeddings_configured,
)
from flowdesk_core.models.conversation import Conversation, Message
from flowdesk_core.models.retrieval_chunk import RetrievalChunk

router = APIRouter(prefix="/me/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    agent: str | None
    symbols: list[str] | None
    message_count: int
    updated_at: str


class MessageOut(BaseModel):
    role: str
    content: str | None
    tools_used: list[str] | None
    created_at: str


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


class RenameIn(BaseModel):
    title: str


class ConversationSearchHit(BaseModel):
    id: str  # conversation id (open via resume)
    similarity: float
    summary: str
    when: str | None


def _uid(current_user: dict) -> UUID:
    return UUID(current_user["sub"])


async def _owned(db: AsyncSession, cid: str, uid: UUID) -> Conversation:
    try:
        conv = await db.get(Conversation, UUID(cid))
    except (ValueError, TypeError):
        conv = None
    if conv is None or conv.keycloak_id != uid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    uid = _uid(current_user)
    rows = (
        (
            await db.execute(
                select(Conversation)
                .where(Conversation.keycloak_id == uid)
                .order_by(Conversation.updated_at.desc())
                .limit(max(1, min(limit, 200)))
            )
        )
        .scalars()
        .all()
    )
    return [
        ConversationSummary(
            id=str(c.id),
            title=c.title,
            agent=c.agent,
            symbols=c.symbols,
            message_count=c.message_count,
            updated_at=c.updated_at.isoformat(),
        )
        for c in rows
    ]


@router.get("/search", response_model=list[ConversationSearchHit])
async def search_conversations(
    q: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
):
    """Semantic search over the caller's own past conversations (owner-scoped).
    Powers the 'recall' UI. Returns [] when empty/unconfigured (never errors)."""
    uid = _uid(current_user)
    if not q or not q.strip() or not embeddings_configured():
        return []
    try:
        qvec = await embed_query(q.strip())
    except EmbeddingError:
        return []
    dist = RetrievalChunk.embedding.cosine_distance(qvec)
    rows = (
        await db.execute(
            select(RetrievalChunk, dist.label("d"))
            .where(
                RetrievalChunk.model == embedding_model_id(),
                RetrievalChunk.source_type == "conversation",
                RetrievalChunk.owner_id == uid,
            )
            .order_by(dist)
            .limit(max(1, min(limit, 20)))
        )
    ).all()
    return [
        ConversationSearchHit(
            id=ch.source_ref or "",
            similarity=round(1.0 - float(d), 3),
            summary=ch.content or "",
            when=ch.published_at.isoformat() if ch.published_at else None,
        )
        for ch, d in rows
        if ch.source_ref
    ]


@router.get("/{cid}", response_model=ConversationDetail)
async def get_conversation(
    cid: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    uid = _uid(current_user)
    conv = await _owned(db, cid, uid)
    msgs = (
        (
            await db.execute(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
            )
        )
        .scalars()
        .all()
    )
    return ConversationDetail(
        id=str(conv.id),
        title=conv.title,
        agent=conv.agent,
        symbols=conv.symbols,
        message_count=conv.message_count,
        updated_at=conv.updated_at.isoformat(),
        messages=[
            MessageOut(
                role=m.role,
                content=m.content,
                tools_used=m.tools_used,
                created_at=m.created_at.isoformat(),
            )
            for m in msgs
        ],
    )


@router.patch("/{cid}", response_model=ConversationSummary)
async def rename_conversation(
    cid: str,
    body: RenameIn,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    uid = _uid(current_user)
    conv = await _owned(db, cid, uid)
    conv.title = (body.title or "").strip()[:200] or conv.title
    await db.commit()
    return ConversationSummary(
        id=str(conv.id),
        title=conv.title,
        agent=conv.agent,
        symbols=conv.symbols,
        message_count=conv.message_count,
        updated_at=conv.updated_at.isoformat(),
    )


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    cid: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    uid = _uid(current_user)
    conv = await _owned(db, cid, uid)
    await db.execute(delete(Conversation).where(Conversation.id == conv.id))
    await db.commit()
