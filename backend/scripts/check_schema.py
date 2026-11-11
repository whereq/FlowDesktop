"""Static schema check — the migrations vs the models, with no database.

Alembic owns the schema; this is a safety net that needs neither a running
Postgres nor the pgvector extension, so it can run in CI and on any machine.

It renders every migration to SQL in offline mode, parses the result, applies
the ALTER statements from the follow-up revisions, and compares the result
against what the SQLAlchemy models declare — table names, column names,
column types and nullability.

Usage:
    python scripts/check_schema.py       # exit 1 on drift, 0 if clean
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import flowdesk_core.models  # noqa: F401,E402  — register every model
from flowdesk_core.database import Base  # noqa: E402

CREATE_RE = re.compile(r"CREATE TABLE (\w+) \((.*?)\n\);", re.DOTALL)
COL_RE = re.compile(r"^\s*(\w+)\s+(.+?)( NOT NULL)?,?\s*$", re.DOTALL)
ALTER_DROP_NOTNULL_RE = re.compile(
    r"ALTER TABLE (\w+) ALTER COLUMN (\w+) DROP NOT NULL;", re.IGNORECASE
)
ALTER_TYPE_RE = re.compile(r"ALTER TABLE (\w+) ALTER COLUMN (\w+) TYPE (.+?);", re.IGNORECASE)

#: Alembic's own bookkeeping table — not a model, and not created by a
#: migration's create_table().
EXCLUDED_TABLES = {"alembic_version"}


def migration_ddl() -> str:
    """Render every migration to SQL without touching a database."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout[-3000:] + "\n")
        sys.stderr.write(result.stderr[-3000:] + "\n")
        raise SystemExit("alembic --sql failed")
    return result.stdout


def parse_ddl(ddl: str) -> dict[str, dict[str, dict]]:
    """Return ``{table: {column: {"type": str, "nullable": bool}}}``."""
    tables: dict[str, dict[str, dict]] = {}

    for table, body in CREATE_RE.findall(ddl):
        cols: dict[str, dict] = {}
        for raw in body.splitlines():
            line = raw.strip()
            # SQL keywords render UPPERCASE, column names lowercase — so this
            # check must be case-sensitive. ("constraints" is a real column
            # name in investor_profile, not a table constraint.)
            if not line or line.startswith(
                ("CONSTRAINT ", "PRIMARY KEY", "UNIQUE", "CHECK ", "FOREIGN KEY")
            ):
                continue
            m = COL_RE.match(line)
            if not m:
                continue
            name, coltype, notnull = m.group(1), m.group(2).strip(), m.group(3)
            cols[name] = {"type": coltype, "nullable": notnull is None}
        tables[table] = cols

    for table, col in ALTER_DROP_NOTNULL_RE.findall(ddl):
        if table in tables and col in tables[table]:
            tables[table][col]["nullable"] = True

    for table, col, newtype in ALTER_TYPE_RE.findall(ddl):
        if table in tables and col in tables[table]:
            tables[table][col]["type"] = newtype.strip()

    return tables


def _norm(s: str) -> str:
    """Normalise a rendered SQL type so equivalent forms compare equal."""
    s = re.sub(r"\s+", "", s or "").upper()
    # A server default is not part of the type.
    s = re.sub(r"DEFAULT.*$", "", s)
    # SERIAL / BIGSERIAL are auto-incrementing INTEGER / BIGINT.
    if s == "SERIAL":
        s = "INTEGER"
    elif s == "BIGSERIAL":
        s = "BIGINT"
    return s


def _dialect():
    from sqlalchemy.dialects import postgresql

    return postgresql.dialect()


def main() -> int:
    ddl = migration_ddl()
    mig = parse_ddl(ddl)
    meta = Base.metadata

    problems: list[str] = []

    mig_tables = set(mig) - EXCLUDED_TABLES
    meta_tables = set(meta.tables)

    for t in sorted(meta_tables - mig_tables):
        problems.append(f"table in the models but not in the migrations: {t}")
    for t in sorted(mig_tables - meta_tables):
        problems.append(f"table in the migrations but not in the models: {t}")

    for t in sorted(meta_tables & mig_tables):
        mig_cols = mig[t]
        meta_cols = {c.name: c for c in meta.tables[t].columns}
        for c in sorted(set(meta_cols) - set(mig_cols)):
            problems.append(f"{t}: column in the model but not in the migration: {c}")
        for c in sorted(set(mig_cols) - set(meta_cols)):
            problems.append(f"{t}: column in the migration but not in the model: {c}")
        for c in sorted(set(meta_cols) & set(mig_cols)):
            model_notnull = not meta_cols[c].nullable
            mig_notnull = not mig_cols[c]["nullable"]
            if model_notnull != mig_notnull:
                problems.append(
                    f"{t}.{c}: nullability differs — "
                    f"model nullable={meta_cols[c].nullable}, "
                    f"migration nullable={mig_cols[c]['nullable']}"
                )
            model_type = _norm(meta_cols[c].type.compile(dialect=_dialect()))
            mig_type = _norm(mig_cols[c]["type"])
            if model_type != mig_type:
                problems.append(f"{t}.{c}: type differs — model={model_type}, migration={mig_type}")

    print(f"tables in the migrations : {len(mig_tables)}")
    print(f"tables in the models     : {len(meta_tables)}")
    print(f"columns compared         : {sum(len(v) for v in mig.values())}")
    print()
    if problems:
        print(f"SCHEMA DRIFT — {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("SCHEMA OK — the migrations produce exactly what the models declare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
