"""Structured JSON logging for the FlowDesktop collector.

Produces one JSON object per line to stdout, compatible with the PLG stack
(Fluent Bit json_message parser → Loki → Grafana).

Standard fields on every line:
  timestamp, level, service, env, message, logger

Contextual fields added via ``extra={...}`` in individual log calls:
  operation, provider, symbol, error_type, duration_ms, etc.
"""

import json
import logging
import os
import sys
import traceback
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def __init__(self, service: str = "flowdesk-collector", env: str = "dev"):
        super().__init__()
        self._service = service
        self._env = env
        # Fields that are part of the standard LogRecord and should NOT be
        # forwarded as extra context fields.
        self._builtin_attrs = frozenset(
            logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
        ) | {"message", "msg"}

    _LEVEL_MAP = {
        "DEBUG": "debug",
        "INFO": "info",
        "WARNING": "warn",
        "ERROR": "error",
        "CRITICAL": "fatal",
    }

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).strftime(
                "%Y-%m-%dT%H:%M:%S."
            )
            + f"{int(record.msecs):03d}Z",
            "level": self._LEVEL_MAP.get(record.levelname, "info"),
            "service": self._service,
            "env": self._env,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge extra fields passed via ``logger.info("msg", extra={...})``
        for key, val in record.__dict__.items():
            if key not in self._builtin_attrs and key not in obj:
                obj[key] = val

        # Attach exception traceback as a single string
        if record.exc_info and record.exc_info[1] is not None:
            obj["exception"] = "".join(traceback.format_exception(*record.exc_info)).rstrip()

        return json.dumps(obj, default=str, ensure_ascii=False)


def setup_logging(
    service: str | None = None,
    env: str | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure the root logger with JSON output to stdout.

    Call once at the collector entry point before any other imports that
    create loggers.  All child loggers inherit the JSON formatter.

    ``service`` defaults to the ``SERVICE_NAME`` env var, else ``flowdesk-collector``.
    Consumers that reuse this package (e.g. flowdesk-worker) pass their own name.
    """
    if service is None:
        service = os.getenv("SERVICE_NAME", "flowdesk-collector")
    if env is None:
        env = os.getenv("ENV", "dev")

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (e.g. basicConfig defaults)
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service=service, env=env))
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for name in ("urllib3", "aiohttp", "akshare", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def classify_error(exc: BaseException) -> str:
    """Map exception types to standardised error_type values."""
    import asyncio

    import aiohttp

    if isinstance(exc, (ConnectionError, aiohttp.ClientConnectorError)):
        return "connection_error"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, aiohttp.ServerTimeoutError)):
        return "timeout"
    if isinstance(exc, aiohttp.ClientResponseError):
        status = exc.status
        if status == 429:
            return "rate_limit"
        if 400 <= status < 500:
            return "client_error"
        if 500 <= status < 600:
            return "server_error"
        return "http_error"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "parse_error"
    return "unknown_error"
