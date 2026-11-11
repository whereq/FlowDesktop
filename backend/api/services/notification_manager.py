"""Real-time notification delivery via WebSocket + pg_notify.

Architecture:
  Collector jobs call `emit_notification(db, keycloak_id, ...)` (from
  flowdesk.notifications) which:
    1. Writes a UserNotification row to the DB.
    2. Sends a pg_notify on channel "user_notifications" with the payload JSON.

  A background asyncpg listener task (started in main.py lifespan) receives
  those NOTIFY events and pushes them to any connected WebSocket clients via
  NotificationManager.

  Clients connect to:
    WS /api/v1/me/notifications/ws
  and receive JSON payloads whenever a new notification arrives for them.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

# emit_notification lives in flowdesk.notifications so the collector container
# (which does not import from api/) can also use it.
from flowdesk_core.notifications import emit_notification  # re-export for convenience  # noqa: F401

logger = logging.getLogger(__name__)


class NotificationManager:
    """In-process registry of active WebSocket connections.

    One singleton lives in main.py and is shared by the WS endpoint
    and the pg_notify listener task.
    """

    def __init__(self) -> None:
        # keycloak_id (str) → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)
        logger.info("WS connected: user=%s total=%d", user_id, len(self._connections[user_id]))

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        self._connections[user_id].discard(websocket)
        if not self._connections[user_id]:
            del self._connections[user_id]
        logger.info("WS disconnected: user=%s", user_id)

    async def push(self, user_id: str, payload: dict) -> None:
        """Push a JSON payload to all WebSocket connections for a user."""
        sockets = list(self._connections.get(user_id, []))
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    def has_connections(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))


# Module-level singleton — imported by main.py lifespan and WS route
notification_manager = NotificationManager()


# ---------------------------------------------------------------------------
# pg_notify listener — runs as a background task in main.py lifespan
# ---------------------------------------------------------------------------


async def start_pg_listener(database_url: str) -> None:
    """Listen on the 'user_notifications' channel and push to WS clients.

    Converts postgresql+asyncpg:// URL to asyncpg's plain postgresql:// format.
    Reconnects automatically if the connection drops.
    """
    import asyncpg

    # asyncpg needs postgresql:// not postgresql+asyncpg://
    pg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    while True:
        try:
            conn = await asyncpg.connect(pg_url)
            logger.info("pg_notify listener connected")

            async def _on_notification(connection, pid, channel, payload):
                try:
                    data = json.loads(payload)
                    user_id = data.get("keycloak_id")
                    if user_id:
                        await notification_manager.push(user_id, data)
                except Exception as exc:
                    logger.warning("pg_notify handler error: %s", exc)

            await conn.add_listener("user_notifications", _on_notification)

            # Keep the connection alive; exit loop only on explicit cancellation
            while True:
                await asyncio.sleep(30)
                await conn.execute("SELECT 1")  # heartbeat

        except asyncio.CancelledError:
            logger.info("pg_notify listener cancelled")
            return
        except Exception as exc:
            logger.error("pg_notify listener error, reconnecting in 5s: %s", exc)
            await asyncio.sleep(5)
