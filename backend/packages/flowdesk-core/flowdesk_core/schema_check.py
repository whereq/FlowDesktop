"""Schema drift detection — compare the SQLAlchemy models to the live database.

Alembic owns the schema; this is a safety net, not a replacement. On a shared
database a `stamp` without the matching `upgrade` (or a manual change) can leave
the recorded `alembic_version` ahead of the actual DDL — a silent drift that only
surfaces when a query finally hits the missing table/column (which is exactly how
the absent `shadow_trades` table was discovered). Running this after
`alembic upgrade head` in the deploy makes that drift loud and immediate.

Only model-declared tables/columns the DB is *missing* are reported — that is the
failure mode that breaks reads. Extra tables in the DB (other apps share
the same database) are intentionally ignored.

Usage:
    python -m flowdesk.schema_check       # exit 1 if drift, 0 if clean
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import inspect

import flowdesk_core.models  # noqa: F401 — register every model on Base.metadata
from flowdesk_core.database import Base, async_engine


def _collect_drift(sync_conn) -> dict:
    insp = inspect(sync_conn)
    db_tables = set(insp.get_table_names())
    missing_tables = sorted(set(Base.metadata.tables) - db_tables)
    column_drift: dict[str, list[str]] = {}
    for name, table in Base.metadata.tables.items():
        if name not in db_tables:
            continue
        db_cols = {c["name"] for c in insp.get_columns(name)}
        missing = sorted({c.name for c in table.columns} - db_cols)
        if missing:
            column_drift[name] = missing
    return {"missing_tables": missing_tables, "column_drift": column_drift}


async def find_schema_drift() -> dict:
    """Return {'missing_tables': [...], 'column_drift': {table: [cols]}}."""
    async with async_engine.connect() as conn:
        return await conn.run_sync(_collect_drift)


def has_drift(drift: dict) -> bool:
    return bool(drift["missing_tables"] or drift["column_drift"])


def format_drift(drift: dict) -> str:
    lines = []
    if drift["missing_tables"]:
        lines.append("  missing tables: " + ", ".join(drift["missing_tables"]))
    for table, cols in drift["column_drift"].items():
        lines.append(f"  {table} missing columns: " + ", ".join(cols))
    return "\n".join(lines)


async def _main() -> int:
    drift = await find_schema_drift()
    if not has_drift(drift):
        print("schema OK — live DB matches all models")
        return 0
    print("SCHEMA DRIFT DETECTED (models declare these, DB lacks them):")
    print(format_drift(drift))
    print(
        "\nThe recorded alembic_version is likely ahead of the applied DDL. "
        "Reconcile the schema (create the missing tables/columns to match the "
        "models/migrations) before relying on the affected features."
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
