"""Server-side conversation persistence + rolling semantic summary (M1+M2).

Opt-in: only engaged when /chat passes a conversation_id (or creates one). All
writes are best-effort and isolated in their own session so persistence can never
break a chat response. See docs/design/RFC_NOVA_MEMORY_CONTINUITY.md.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.database import AsyncSessionLocal
from flowdesk_core.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)

# Regenerate the rolling summary once this many messages have accrued since the
# last summary; fold in the most recent messages each time.
_SUMMARY_EVERY = 6
_SUMMARY_WINDOW = 20  # most-recent messages fed to the summarizer

_SUMMARY_SYSTEM = (
    "You maintain a concise running summary of an ongoing investment chat between "
    "a user and NOVA (a markets analyst). Given the previous summary and the latest "
    "messages, produce an UPDATED summary (<=180 words, plain text, no preamble) that "
    "preserves: what the user is trying to do, tickers/sectors discussed, key figures "
    "or conclusions NOVA gave, and any stated preferences/constraints. Be factual and "
    "compact; drop small talk."
)


def _title_from(text: str) -> str:
    t = " ".join((text or "").split())
    return (t[:80] + "…") if len(t) > 80 else (t or "New conversation")


async def get_or_create(
    db: AsyncSession,
    user_id: str,
    conversation_id: str | None,
    *,
    agent: str | None,
    symbols: list[str] | None,
    first_text: str,
) -> Conversation | None:
    """Load the caller's conversation (ownership-checked) or create a new one.
    Returns None on any failure (caller falls back to stateless behavior)."""
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None
    try:
        if conversation_id:
            conv = await db.scalar(
                select(Conversation).where(
                    Conversation.id == uuid.UUID(str(conversation_id)),
                    Conversation.keycloak_id == uid,
                )
            )
            return conv  # None if not found / not owned
        conv = Conversation(
            keycloak_id=uid,
            title=_title_from(first_text),
            agent=agent,
            symbols=symbols or None,
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_or_create conversation failed: %s", exc)
        return None


async def persist_turn(
    *,
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    tools_used: list[str] | None,
    agent: str | None,
    symbols: list[str] | None,
) -> None:
    """Append the user + assistant messages and bump counters; refresh the
    rolling summary when due. Best-effort; isolated session."""
    if not conversation_id or not assistant_text:
        return
    try:
        cid = uuid.UUID(str(conversation_id))
    except (ValueError, TypeError):
        return
    try:
        async with AsyncSessionLocal() as session:
            conv = await session.get(Conversation, cid)
            if conv is None:
                return
            session.add(Message(conversation_id=cid, role="user", content=user_text))
            session.add(
                Message(
                    conversation_id=cid,
                    role="assistant",
                    content=assistant_text,
                    tools_used=tools_used or None,
                )
            )
            conv.message_count = (conv.message_count or 0) + 2
            if agent and not conv.agent:
                conv.agent = agent
            if symbols and not conv.symbols:
                conv.symbols = symbols
            await session.commit()

            if (conv.message_count - (conv.summary_turns or 0)) >= _SUMMARY_EVERY:
                await _refresh_summary(session, conv)
    except Exception as exc:  # noqa: BLE001
        logger.warning("persist_turn failed: %s", exc)


async def _refresh_summary(session: AsyncSession, conv: Conversation) -> None:
    """Fold recent messages into the rolling summary via the cheap platform LLM."""
    from flowdesk_core.llm_platform import call_platform_llm

    rows = (
        await session.execute(
            select(Message.role, Message.content)
            .where(Message.conversation_id == conv.id)
            .order_by(desc(Message.id))
            .limit(_SUMMARY_WINDOW)
        )
    ).all()
    if not rows:
        return
    recent = "\n".join(f"{r.role}: {(r.content or '').strip()[:500]}" for r in reversed(rows))
    user_block = (
        f"Previous summary:\n{conv.rolling_summary or '(none yet)'}\n\nLatest messages:\n{recent}"
    )
    try:
        summary = await call_platform_llm(
            _SUMMARY_SYSTEM, user_block, max_tokens=320, temperature=0.3
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("summary LLM failed: %s", exc)
        return
    if summary and summary.strip():
        conv.rolling_summary = summary.strip()
        conv.summary_turns = conv.message_count
        await session.commit()
