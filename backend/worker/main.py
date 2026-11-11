"""FlowDesktop product-jobs worker.

Runs the scheduled jobs that depend on flowdesk's `api.services` and therefore
CANNOT run in a standalone data collector:

  - run_due_agent_schedules  (NOVA scheduled agents → api.services.skills)
  - run_sim_order_matcher     (paper-trading matcher → api.services.simulation)
  - run_sim_snapshots         (paper-trading equity snapshots)

Everything else — all data collection — runs in the `flowdesk-collector`
package, which may be deployed separately. This worker reuses the same job
bodies from that package, so there is a single source of truth for both the
logic and the schedule; here they execute in the application's runtime,
where `api.services` is importable.

Entry point: `python -m worker.main`
"""

import asyncio
import logging
import os
import signal
import socket

from flowdesk_collector.logging_config import setup_logging

setup_logging(service="flowdesk-worker")

# Bound blocking sockets, same rationale as the platform collector: a wedged
# sync provider/LLM call must not hang a worker thread forever.
socket.setdefaulttimeout(int(os.getenv("COLLECTOR_SOCKET_TIMEOUT", "60")))

from flowdesk_collector.scheduler import FlowDesktopScheduler  # noqa: E402
from flowdesk_core.database import init_db  # noqa: E402

logger = logging.getLogger(__name__)


async def main() -> None:
    _op = {"operation": "startup"}
    logger.info("Starting FlowDesktop product-jobs worker", extra=_op)

    await init_db()

    scheduler = FlowDesktopScheduler()

    # Register + start ONLY the flowdesk product jobs (no data-collection jobs —
    # those run in the platform collector, so this never double-collects).
    scheduler.start_product_only()

    stop_event = asyncio.Event()

    def _signal_handler(sig, frame):
        logger.info("Received shutdown signal", extra={"operation": "shutdown"})
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        await stop_event.wait()
    finally:
        scheduler.stop()
        logger.info("FlowDesktop worker shutdown complete", extra={"operation": "shutdown"})


if __name__ == "__main__":
    asyncio.run(main())
