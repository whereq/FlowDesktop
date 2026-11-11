"""RetrievalChunk — embedded text for NOVA semantic/hybrid retrieval.

One row per embedded chunk of FlowDesktop's own content (news/signals now,
filings/sector narratives later). Populated by the EmbeddingIndexer collector
job; queried by the semantic_news_search tool via cosine similarity over the
pgvector HNSW index. See docs/design/RFC_NOVA_SEMANTIC_RETRIEVAL.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.config import get_settings
from flowdesk_core.database import Base

# Dimension is fixed at the table level (migration 023 = 1536). Keep the model
# in sync with settings so a deliberate model change is a single, visible edit.
_EMBEDDING_DIM = get_settings().embedding_dim


class RetrievalChunk(Base):
    __tablename__ = "retrieval_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "chunk_index",
            "model",
            name="uq_chunk_source_model",
        ),
        Index("ix_chunks_published", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'news' | 'signal' | 'sector' | 'filing'
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)

    # Denormalized metadata for cheap pre/post-filtering (no join on the hot path)
    symbols: Mapped[list[str] | None] = mapped_column(ARRAY(String(20)))
    sectors: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    regions: Mapped[list[str] | None] = mapped_column(ARRAY(String(10)))
    sentiment: Mapped[float | None] = mapped_column(Float)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    lang: Mapped[str | None] = mapped_column(String(5))

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # Owner scoping: NULL = global (news/signals); set = private (a user's
    # conversations). source_ref holds a non-integer source key (conversation UUID).
    owner_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RetrievalChunk {self.source_type}:{self.source_id}#{self.chunk_index}>"
