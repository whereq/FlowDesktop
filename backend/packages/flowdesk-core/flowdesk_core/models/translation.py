"""Translation memory — the store behind example.com's native bilingual mirroring.

Every collected text string gets a copy in the other language (EN↔中文). Keyed by
a hash of the *source text* (not by which row it came from), so an identical string
("China", "Technology") is translated once via MiniMax and reused everywhere it
appears — cheap, deterministic, and language-agnostic to serve.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (
        UniqueConstraint("source_hash", "target_lang", name="uq_translation_hash_lang"),
        Index("ix_translation_hash", "source_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_hash: Mapped[str] = mapped_column(String(32), nullable=False)  # md5(source_text)
    source_lang: Mapped[str] = mapped_column(String(5), nullable=False)  # en | zh
    target_lang: Mapped[str] = mapped_column(String(5), nullable=False)  # zh | en
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str] = mapped_column(String(24), nullable=False, default="minimax")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
