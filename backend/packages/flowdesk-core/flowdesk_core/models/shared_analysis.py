"""Publicly shareable NOVA analysis snapshots.

A user shares a NOVA answer → we store an immutable snapshot with a slug, served
as a server-rendered, SEO-friendly page at /s/{slug} (and listed in sitemap.xml).
This turns AI output into a shareable, indexable acquisition surface.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class SharedAnalysis(Base):
    """One public snapshot of a NOVA analysis."""

    __tablename__ = "shared_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<SharedAnalysis {self.slug} {self.symbol}>"
