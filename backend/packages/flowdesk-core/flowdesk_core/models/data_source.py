"""Tracks the 3rd-party data sources integrated with example.com.

Powers the /v1/data-sources meta endpoint - lets the portal show
which sources are live, how many records each one has cached, when
they were last updated, and whether the API key is configured.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class DataSource(Base):
    """Registry of integrated 3rd-party data sources.

    One row per source (FRED, OpenCorporates, Eurostat, OpenAlex,
    Weather, Food, Geo, FEC, Sports, ...). Updated by the operator
    when a new source is integrated; not auto-populated by the
    source's own fetch_log tables (those are per-source).
    """

    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(40), nullable=False, index=True, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    api_base: Mapped[str] = mapped_column(String(200), nullable=True)
    api_key_env_var: Mapped[str] = mapped_column(String(60), nullable=True)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rate_limit: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active, down, beta
    # Coverage - what verticals does this source serve
    primary_domain: Mapped[str | None] = mapped_column(String(80), index=True)
    secondary_domains: Mapped[str | None] = mapped_column(String(200))  # comma-separated
    # Quick stats - updated by the operator or by a stats refresh job
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    curated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime)
    # Documentation links
    docs_url: Mapped[str | None] = mapped_column(String(200))
    portal_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    # Sort order for the portal surface
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
