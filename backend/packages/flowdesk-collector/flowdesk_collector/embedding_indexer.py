"""EmbeddingIndexer — keeps retrieval_chunks in sync for NOVA semantic search.

Each run embeds market_signals that don't yet have a chunk for the active
embedding model, building one chunk per language (en/zh) so each is
independently searchable. Idempotent via the uq_chunk_source_model constraint;
a single failure skips that batch slice, never aborts the run.

See docs/design/RFC_NOVA_SEMANTIC_RETRIEVAL.md.
"""

from __future__ import annotations

import logging
import time
import uuid as _uuid
from datetime import datetime

from sqlalchemy import and_, exists, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from flowdesk_core.database import AsyncSessionLocal
from flowdesk_core.embeddings import (
    EmbeddingError,
    embed_texts,
    embedding_model_id,
    is_configured,
)
from flowdesk_core.models.conversation import Conversation
from flowdesk_core.models.market_intelligence import MarketNewsItem, MarketSignal
from flowdesk_core.models.retrieval_chunk import RetrievalChunk

logger = logging.getLogger(__name__)

_EMBED_SUBBATCH = 64  # texts per provider call


def _chunks_for_signal(signal: MarketSignal, news: MarketNewsItem) -> list[dict]:
    """Build the (language-split) chunk rows for one signal, minus the vector.

    Shared denormalized metadata lets the retriever filter without a join.
    """
    symbols = list(
        dict.fromkeys((signal.symbols_mentioned or []) + (signal.symbols_impacted or []))
    )
    regions = signal.regions or ([news.region] if news.region else [])
    base = {
        "source_type": "signal",
        "source_id": signal.id,
        "symbols": symbols or None,
        "sectors": signal.sectors_affected or None,
        "regions": regions or None,
        "sentiment": signal.sentiment,
        "published_at": news.published_at,
        "model": embedding_model_id(),
    }

    rows: list[dict] = []
    en = (news.title or "").strip()
    if signal.summary_en:
        en = f"{en}\n{signal.summary_en}".strip()
    if en:
        rows.append({**base, "chunk_index": 0, "content": en, "lang": "en"})
    if signal.summary_zh and signal.summary_zh.strip():
        rows.append({**base, "chunk_index": 1, "content": signal.summary_zh.strip(), "lang": "zh"})
    return rows


def _chunks_for_filing(filing) -> list[dict]:
    """Split one filing's narrative into capped, fixed-size chunks for embedding.

    Each chunk is prefixed with a small header (symbol/form/date) so a retrieved
    snippet carries its own provenance. Sizes/caps come from settings.
    """
    from datetime import datetime as _dt

    from flowdesk_core.config import get_settings

    s = get_settings()
    size, cap = s.filings_chunk_chars, s.filings_max_chunks_per_doc
    text = filing.content or ""
    header = f"{filing.symbol} {filing.form} {filing.filing_date}"
    published = _dt.combine(filing.filing_date, _dt.min.time()) if filing.filing_date else None
    base = {
        "source_type": "filing",
        "source_id": filing.id,
        "symbols": [filing.symbol],
        "published_at": published,
        "model": embedding_model_id(),
        "lang": "en",
    }
    rows: list[dict] = []
    for i in range(cap):
        start = i * size
        if start >= len(text):
            break
        rows.append(
            {**base, "chunk_index": i, "content": f"[{header}] {text[start : start + size]}"}
        )
    return rows


async def index_filings(batch_size: int = 8) -> int:
    """Embed not-yet-indexed company_filings into retrieval_chunks (source_type=
    'filing'). Small batch — each filing fans out into many chunks. Returns rows.
    Idempotent via uq_chunk_source_model; no-op when embeddings are unconfigured."""
    if not is_configured():
        return 0
    from flowdesk_core.models.company_filing import CompanyFiling

    model = embedding_model_id()
    async with AsyncSessionLocal() as session:
        already = (
            select(RetrievalChunk.id)
            .where(
                and_(
                    RetrievalChunk.source_type == "filing",
                    RetrievalChunk.source_id == CompanyFiling.id,
                    RetrievalChunk.model == model,
                )
            )
            .correlate(CompanyFiling)
        )
        pending = (
            (
                await session.execute(
                    select(CompanyFiling)
                    .where(~exists(already))
                    .order_by(CompanyFiling.filing_date.desc())
                    .limit(batch_size)
                )
            )
            .scalars()
            .all()
        )

    if not pending:
        return 0

    work: list[dict] = []
    for f in pending:
        work.extend(_chunks_for_filing(f))
    if not work:
        return 0

    vectors: list[list[float]] = []
    try:
        for i in range(0, len(work), _EMBED_SUBBATCH):
            slice_texts = [w["content"] for w in work[i : i + _EMBED_SUBBATCH]]
            vectors.extend(await embed_texts(slice_texts, kind="db"))
    except EmbeddingError as exc:
        logger.warning("index_filings: provider error, will retry next run: %s", exc)
        return 0

    written = 0
    async with AsyncSessionLocal() as session:
        for w, vec in zip(work, vectors, strict=False):
            await session.execute(
                pg_insert(RetrievalChunk)
                .values(embedding=vec, **w)
                .on_conflict_do_nothing(constraint="uq_chunk_source_model")
            )
            written += 1
        await session.commit()

    logger.info("index_filings: %d filing(s) → %d chunk(s)", len(pending), written)
    return written


async def index_pending_embeddings(batch_size: int = 256) -> int:
    """Embed up to `batch_size` not-yet-indexed signals. Returns rows written.

    No-op (logs once) when embeddings are unconfigured, so the collector never
    crashes on a missing embedding key.
    """
    if not is_configured():
        logger.info("embedding_index: skipped — embeddings not configured")
        return 0

    model = embedding_model_id()
    t0 = time.monotonic()

    # Select signals with no chunk for the active model yet (newest first).
    async with AsyncSessionLocal() as session:
        already = (
            select(RetrievalChunk.id)
            .where(
                and_(
                    RetrievalChunk.source_type == "signal",
                    RetrievalChunk.source_id == MarketSignal.id,
                    RetrievalChunk.model == model,
                )
            )
            .correlate(MarketSignal)
        )
        result = await session.execute(
            select(MarketSignal, MarketNewsItem)
            .join(MarketNewsItem, MarketSignal.news_item_id == MarketNewsItem.id)
            .where(~exists(already))
            .order_by(MarketNewsItem.published_at.desc())
            .limit(batch_size)
        )
        pending = result.all()

    if not pending:
        logger.info("embedding_index: nothing to embed")
        return 0

    # Flatten to chunk rows, embed in sub-batches.
    work: list[dict] = []
    for signal, news in pending:
        work.extend(_chunks_for_signal(signal, news))
    if not work:
        return 0

    vectors: list[list[float]] = []
    try:
        for i in range(0, len(work), _EMBED_SUBBATCH):
            slice_texts = [w["content"] for w in work[i : i + _EMBED_SUBBATCH]]
            vectors.extend(await embed_texts(slice_texts, kind="db"))
    except EmbeddingError as exc:
        logger.warning("embedding_index: provider error, will retry next run: %s", exc)
        return 0

    written = 0
    async with AsyncSessionLocal() as session:
        for w, vec in zip(work, vectors, strict=False):
            stmt = (
                pg_insert(RetrievalChunk)
                .values(embedding=vec, **w)
                .on_conflict_do_nothing(constraint="uq_chunk_source_model")
            )
            await session.execute(stmt)
            written += 1
        await session.commit()

    logger.info(
        "embedding_index complete",
        extra={
            "operation": "embedding_index",
            "signals": len(pending),
            "chunks_written": written,
            "model": model,
            "latency_ms": int((time.monotonic() - t0) * 1000),
        },
    )
    return written


def _uuid_to_bigint(u: _uuid.UUID) -> int:
    """Stable positive 63-bit int from a UUID (fits signed BIGINT source_id)."""
    return int.from_bytes(u.bytes[:8], "big") >> 1


async def index_conversation_summaries(batch_size: int = 128) -> int:
    """Embed each conversation's rolling_summary into retrieval_chunks (owner-scoped)
    so NOVA can semantically search the user's OWN past conversations. Upserts;
    re-embeds when a conversation has been updated since its chunk. Returns rows."""
    if not is_configured():
        return 0
    model = embedding_model_id()

    async with AsyncSessionLocal() as session:
        convs = (
            (
                await session.execute(
                    select(Conversation)
                    .where(Conversation.rolling_summary.isnot(None))
                    .order_by(Conversation.updated_at.desc())
                    .limit(batch_size)
                )
            )
            .scalars()
            .all()
        )
        if not convs:
            return 0
        refs = [str(c.id) for c in convs]
        existing = (
            await session.execute(
                select(RetrievalChunk.source_ref, RetrievalChunk.created_at).where(
                    RetrievalChunk.source_type == "conversation",
                    RetrievalChunk.model == model,
                    RetrievalChunk.source_ref.in_(refs),
                )
            )
        ).all()
        fresh = dict(existing)

    # (Re)embed conversations with no chunk yet, or whose chunk is stale.
    todo = [
        c
        for c in convs
        if str(c.id) not in fresh
        or (c.updated_at and fresh[str(c.id)] and c.updated_at > fresh[str(c.id)])
    ]
    if not todo:
        return 0

    try:
        vecs = await embed_texts([c.rolling_summary for c in todo], kind="db")
    except EmbeddingError as exc:
        logger.warning("conversation_index: provider error, will retry: %s", exc)
        return 0

    written = 0
    async with AsyncSessionLocal() as session:
        for c, vec in zip(todo, vecs, strict=False):
            stmt = (
                pg_insert(RetrievalChunk)
                .values(
                    source_type="conversation",
                    source_id=_uuid_to_bigint(c.id),
                    chunk_index=0,
                    content=c.rolling_summary,
                    embedding=vec,
                    model=model,
                    owner_id=c.keycloak_id,
                    source_ref=str(c.id),
                    symbols=c.symbols or None,
                    published_at=c.updated_at,
                    lang=None,
                )
                .on_conflict_do_update(
                    constraint="uq_chunk_source_model",
                    set_={
                        "embedding": vec,
                        "content": c.rolling_summary,
                        "published_at": c.updated_at,
                        "created_at": datetime.utcnow(),
                    },
                )
            )
            await session.execute(stmt)
            written += 1
        await session.commit()

    logger.info(
        "conversation_index complete",
        extra={"operation": "conversation_index", "conversations": written, "model": model},
    )
    return written


async def backfill_embeddings(max_rounds: int = 80, batch_size: int = 256) -> None:
    """One-shot boot backfill: index in rounds until caught up (or cap hit)."""
    if not is_configured():
        return
    for _ in range(max_rounds):
        n = await index_pending_embeddings(batch_size)
        if n == 0:
            break
