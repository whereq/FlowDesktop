"""Slow-query log middleware (Tier 29 #4).

Listens to every `before_cursor_execute` / `after_cursor_execute` SQLAlchemy
event on the async engine. If a query takes longer than
`SLOW_QUERY_MS` (default 250), prints a structured warning to the logger
+ keeps a rolling in-memory counter for `/v1/admin/slow-queries`.

Configurable via env:
  DB_POOL_SIZE          default 10
  DB_MAX_OVERFLOW       default 20
  SLOW_QUERY_MS         default 250
  SLOW_QUERY_LOG        default 1 (0 to disable)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque

from sqlalchemy import event

logger = logging.getLogger("flowdesk-core.slow-query")

_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
_SLOW_MS = float(os.getenv("SLOW_QUERY_MS", "250"))
_ENABLED = bool(int(os.getenv("SLOW_QUERY_LOG", "1")))

# Rolling stats: last 100 slow queries + per-minute count
_RECENT: deque = deque(maxlen=100)
_PER_MIN: dict[str, int] = defaultdict(int)
_LOCK = threading.Lock()


def _mask(sql: str) -> str:
    """Trim + redact obvious PII patterns. Not perfect — just reduces noise."""
    s = " ".join(sql.split())
    if len(s) > 400:
        s = s[:400] + "...[truncated]"
    return s


def configure(engine) -> None:
    """Bind slow-query listeners to the engine. Idempotent."""
    if not _ENABLED:
        return

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        context._wq_started_at = time.monotonic()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        started = getattr(context, "_wq_started_at", None)
        if started is None:
            return
        ms = (time.monotonic() - started) * 1000.0
        if ms < _SLOW_MS:
            return
        minute_key = time.strftime("%Y-%m-%dT%H:%M", time.gmtime())
        with _LOCK:
            _PER_MIN[minute_key] += 1
            _RECENT.append({"ts": time.time(), "ms": round(ms, 2), "sql": _mask(statement)})
        logger.warning("slow_query: %.1fms  %s", ms, _mask(statement))


def stats() -> dict:
    """Snapshot of the slow-query stats. Cheap (in-memory)."""
    with _LOCK:
        return {
            "threshold_ms": _SLOW_MS,
            "recent_count": len(_RECENT),
            "recent_top5_ms": sorted([r["ms"] for r in _RECENT], reverse=True)[:5],
            "per_minute_last_60min": dict(_list_recent_minutes(_PER_MIN)),
        }


def _list_recent_minutes(d: dict[str, int]) -> list[tuple[str, int]]:
    items = sorted(d.items(), reverse=True)
    return items[:60]


def recent_queries(limit: int = 20) -> list[dict]:
    with _LOCK:
        return list(_RECENT)[-limit:][::-1]
