"""Alembic environment for FlowDesktop.

The database URL always comes from the application settings (``DATABASE_URL``),
never from the config file, so no connection string is ever committed.

Two extensions are required and are created automatically before the first
migration runs:

* ``vector``     — pgvector, used by ``retrieval_chunk.embedding``
* ``pg_trgm``    — trigram indexes for symbol/name search
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Make the application packages importable when alembic is invoked from the
# backend directory.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from flowdesk_core.config import get_settings  # noqa: E402
from flowdesk_core.database import Base  # noqa: E402

# Importing the models package registers every table on Base.metadata.
import flowdesk_core.models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

#: Extensions the schema depends on.
REQUIRED_EXTENSIONS = ("vector", "pg_trgm")


def _database_url() -> str:
    """Resolve the database URL from settings, falling back to the environment."""
    url = get_settings().database_url
    if not url:
        url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL in your environment "
            "or in backend/.env before running migrations."
        )
    return url


def _ensure_extensions(connection) -> None:
    """Create the extensions the schema needs, if the role is allowed to."""
    for ext in REQUIRED_EXTENSIONS:
        try:
            connection.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
        except Exception as exc:  # pragma: no cover - depends on DB privileges
            print(f"[alembic] could not create extension {ext}: {exc}")


def run_migrations_offline() -> None:
    """Run migrations without a live database connection (emit SQL)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Create the required extensions on their own connection and commit them.
    #
    # This must NOT share a connection with the migration run: executing DDL
    # here would auto-begin a transaction, Alembic would then see a
    # transaction already in progress and skip its own commit, and the
    # migration would be silently rolled back when the connection closes.
    with connectable.connect() as ext_conn:
        _ensure_extensions(ext_conn)
        ext_conn.commit()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
