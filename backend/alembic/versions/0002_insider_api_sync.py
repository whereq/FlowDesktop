"""Relax the insider-transaction columns the Data API does not fill.

FlowDesktop now syncs insider Form 4 activity from the whereq.cloud Data API
(`/v1/alt/insider/{symbol}`) instead of parsing EDGAR documents itself. The
API addresses insider activity by ticker and returns a stable platform row id,
but it exposes no CIK.

So:
  * `cik` becomes nullable — a synced row has no CIK.
  * `line_index` becomes bigint — it carries that platform row id, which is
    what keeps `(accession, line_index)` unique and the sync idempotent.

The `cik` column is kept (rather than dropped) so rows parsed from a raw
Form 4 document still fit.

Revision ID: 0002_insider_api_sync
Revises: 0001_initial_schema
Create Date: 2026-11-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_insider_api_sync"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "insider_transactions",
        "cik",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.alter_column(
        "insider_transactions",
        "line_index",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Rows synced from the API have no CIK, so this cannot be reversed while
    # such rows exist — the NOT NULL constraint would fail to apply. Drop the
    # CIK-less rows first, then restore the original column types.
    op.execute("DELETE FROM insider_transactions WHERE cik IS NULL")
    op.alter_column(
        "insider_transactions",
        "line_index",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "insider_transactions",
        "cik",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
