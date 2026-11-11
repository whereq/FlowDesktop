"""Multi-domain spine — the registry that turns example.com from a finance
vertical into a horizontal, multi-domain data cloud.

Three tables:
  * `domains`   — the taxonomy tree (arbitrary depth: Manufacturing → Automotive →
                  Car parts). Adjacency list (parent_id) + materialized `path` for
                  fast subtree queries.
  * `entities`  — the generic per-domain directory (the multi-domain analogue of
                  the finance `stocks` spine). Sparse/young domains live here with
                  JSONB attributes; mature domains may add typed depth tables keyed
                  to entity_id (hybrid strategy).
  * `datasets`  — a first-class catalog of what each domain offers. Registry-driven:
                  /v1/catalog, /v1/status, the playground and MCP read this instead
                  of hardcoding, so adding a domain is *registering datasets*, not
                  editing routers. `source_table` lets /v1/status report freshness
                  for any domain (finance datasets point at their existing tables).

Finance is registered as domain #1 with its datasets pointing at the existing
finance tables — no data migration; `stocks` stays its native spine.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class Domain(Base):
    __tablename__ = "domains"
    __table_args__ = (
        UniqueConstraint("path", name="uq_domain_path"),
        Index("ix_domain_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("domains.id"))
    slug: Mapped[str] = mapped_column(String(60), nullable=False)  # unique within parent
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(120))
    path: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g. manufacturing/automotive/car-parts
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = root
    entity_noun: Mapped[str | None] = mapped_column(
        String(40)
    )  # what an entity is called ("manufacturer")
    entity_noun_cn: Mapped[str | None] = mapped_column(String(40))
    category_slug: Mapped[str | None] = mapped_column(
        String(40)
    )  # cross-cutting Category facet (categories.slug)
    description: Mapped[str | None] = mapped_column(Text)
    description_cn: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("domain_id", "slug", name="uq_entity_domain_slug"),
        Index("ix_entity_domain", "domain_id"),
        Index("ix_entity_name", "name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("domains.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)  # unique within domain
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    identifiers: Mapped[dict | None] = mapped_column(JSON)  # {lei, website, country, ticker, …}
    attributes: Mapped[dict | None] = mapped_column(JSON)  # domain-specific facts
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EntityIdentifier(Base):
    """Crosswalk of stable external identifiers → one entity.

    A unique (scheme, value) means the same real-world thing resolves to one
    entity no matter which source/collector saw it (dedup + source-merge), and
    lets entities link across domains (e.g. a supplier's `ticker` ties to a
    finance stock entity). Descriptive fields (website, country) stay in
    `entities.identifiers` JSONB; this table is the normalized resolution index.
    """

    __tablename__ = "entity_identifiers"
    __table_args__ = (
        UniqueConstraint("scheme", "value", name="uq_entity_ident_scheme_value"),
        Index("ix_entity_ident_entity", "entity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("entities.id"), nullable=False)
    scheme: Mapped[str] = mapped_column(
        String(24), nullable=False
    )  # ticker | wikidata | lei | isin | cik | duns
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("domain_id", "slug", name="uq_dataset_domain_slug"),
        Index("ix_dataset_domain", "domain_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("domains.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_cn: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    description_cn: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(String(40))  # API scope gating it (None = public)
    cadence: Mapped[str | None] = mapped_column(String(40))  # realtime | daily | weekly | …
    source_table: Mapped[str | None] = mapped_column(
        String(80)
    )  # backing table (for /v1/status freshness)
    freshness_column: Mapped[str | None] = mapped_column(
        String(40)
    )  # timestamp col in source_table
    warn_hours: Mapped[int | None] = mapped_column(
        Integer
    )  # /v1/status: operational within this age
    # The upstream feed(s) that PRODUCE this dataset (e.g. the market data
    # API). Curated — the collector knows it in code, the
    # status page shows it to admins. NULL = a static registry with no
    # upstream (crops, manufacturers). NOT served by the public dataset
    # endpoints; it is admin-only on /v1/status/collections.
    source_feed: Mapped[str | None] = mapped_column(String(160))
    # Which SLICE of source_table this dataset owns. Five datasets share
    # `price_series` — fuel-prices, food-prices, energy-prices, home-prices
    # and rents — and each owns a different `domain` of it. Without this
    # every one of them counted the whole table. The filter is SQL, so it
    # is validated by `flowdesk_core.registry.safe_filter` before use.
    # NULL = every row of the table.
    row_filter: Mapped[str | None] = mapped_column(String(200))
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
