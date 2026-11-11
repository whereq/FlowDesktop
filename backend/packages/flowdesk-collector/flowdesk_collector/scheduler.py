"""The FlowDesktop scheduler.

Two roles, one scheduler:

**Collector mode** (the default) runs the data-collection jobs — quotes,
history, SEC filings, insider Form 4, short interest — plus the product jobs.
This is what a self-hosted user runs.

**Product-only mode** runs just the product jobs (scheduled agents, the
simulator matcher, daily equity snapshots). Use this when the data collection
is hosted elsewhere and only the application-side work should run here.

Run it with::

    python -m flowdesk_collector.scheduler            # collector + product jobs
    python -m flowdesk_collector.scheduler --product-only
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import socket

from flowdesk_collector.logging_config import setup_logging

setup_logging(service="flowdesktop-collector")

# Bound blocking sockets — a wedged provider call must not hang a worker
# thread forever.
socket.setdefaulttimeout(int(os.getenv("COLLECTOR_SOCKET_TIMEOUT", "60")))

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402
from apscheduler.triggers.interval import IntervalTrigger  # noqa: E402

from flowdesk_core.config import get_settings  # noqa: E402
from flowdesk_core.database import AsyncSessionLocal, init_db  # noqa: E402

logger = logging.getLogger("flowdesk-collector.scheduler")


class FlowDesktopScheduler:
    """Owns the APScheduler instance and the job catalogue."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False

    # ------------------------------------------------------------------
    # Job bodies
    # ------------------------------------------------------------------

    async def _run(self, name: str, coro_factory):
        """Wrap a job body so a failure is logged, not fatal."""
        try:
            await coro_factory()
        except Exception:
            logger.error("Job %s failed", name, exc_info=True)

    async def job_collect_quotes(self) -> None:
        from flowdesk_collector.collectors.quotes import collect_quotes
        from flowdesk_collector.market_hours import any_market_open

        if not any_market_open():
            logger.info("All markets closed — skipping quote collection")
            return
        async with AsyncSessionLocal() as session:
            await collect_quotes(session)

    async def job_collect_history(self) -> None:
        from flowdesk_collector.collectors.history import collect_history

        async with AsyncSessionLocal() as session:
            await collect_history(session, max_symbols=200)

    async def job_collect_filings(self) -> None:
        from flowdesk_collector.collectors.altdata import collect_filings

        async with AsyncSessionLocal() as session:
            await collect_filings(session)

    async def job_collect_insider(self) -> None:
        from flowdesk_collector.collectors.altdata import collect_insider_transactions

        async with AsyncSessionLocal() as session:
            await collect_insider_transactions(session)

    async def job_collect_short_interest(self) -> None:
        from flowdesk_collector.collectors.altdata import collect_short_interest

        async with AsyncSessionLocal() as session:
            await collect_short_interest(session)

    async def job_seed_universe(self) -> None:
        from flowdesk_collector.collectors.universe import seed_universe
        from flowdesk_collector.provider_registry import seed_provider_status

        async with AsyncSessionLocal() as session:
            await seed_universe(session)
            await seed_provider_status(session)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register_collector_jobs(self) -> None:
        s = self.settings
        add = self.scheduler.add_job

        # Daily UTC plan
        add(
            self._run("seed_universe", self.job_seed_universe),
            trigger=CronTrigger(hour=0, minute=1),
            id="seed_universe",
            name="Seed the symbol universe and provider registry",
            replace_existing=True,
        )

        # Live quotes — only while a market is open
        add(
            self._run("collect_quotes", self.job_collect_quotes),
            trigger=IntervalTrigger(minutes=s.collection_interval_minutes),
            id="collect_quotes",
            name="Collect latest quotes",
            replace_existing=True,
        )

        # History backfill — opportunistic, a few symbols per run
        add(
            self._run("collect_history", self.job_collect_history),
            trigger=IntervalTrigger(hours=4),
            id="collect_history",
            name="Backfill daily history",
            replace_existing=True,
        )

        # Alternative data — SEC is rate-limited, so these run a few times a day
        add(
            self._run("collect_filings", self.job_collect_filings),
            trigger=CronTrigger(hour=2, minute=0),
            id="collect_filings",
            name="Collect SEC filings (10-K/10-Q)",
            replace_existing=True,
        )

        add(
            self._run("collect_insider", self.job_collect_insider),
            trigger=CronTrigger(hour=2, minute=30),
            id="collect_insider",
            name="Collect insider Form 4 transactions",
            replace_existing=True,
        )

        add(
            self._run("collect_short_interest", self.job_collect_short_interest),
            trigger=CronTrigger(hour=3, minute=0),
            id="collect_short_interest",
            name="Collect short-interest snapshots",
            replace_existing=True,
        )

    def _register_product_jobs(self) -> None:
        from flowdesk_collector import product_jobs

        s = self.settings
        add = self.scheduler.add_job

        add(
            self._run("run_due_agent_schedules", product_jobs.run_due_agent_schedules),
            trigger=IntervalTrigger(minutes=5),
            id="run_due_agent_schedules",
            name="Run due scheduled agents and deliver briefs",
            replace_existing=True,
        )

        add(
            self._run("run_sim_order_matcher", product_jobs.run_sim_order_matcher),
            trigger=IntervalTrigger(minutes=s.sim_matcher_interval_minutes),
            id="run_sim_order_matcher",
            name="Simulator: match resting orders",
            replace_existing=True,
        )

        add(
            self._run("run_sim_snapshots", product_jobs.run_sim_snapshots),
            trigger=CronTrigger(hour=22, minute=0),
            id="run_sim_snapshots",
            name="Simulator: daily equity snapshots",
            replace_existing=True,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the collector jobs and the product jobs."""
        if self._running:
            return
        self._register_collector_jobs()
        self._register_product_jobs()
        self.scheduler.start()
        self._running = True
        logger.info("FlowDesktop scheduler started (%d jobs)", len(self.scheduler.get_jobs()))

    def start_product_only(self) -> None:
        """Start only the product jobs — no data collection."""
        if self._running:
            return
        self._register_product_jobs()
        self.scheduler.start()
        self._running = True
        logger.info(
            "FlowDesktop product-jobs scheduler started (%d jobs)",
            len(self.scheduler.get_jobs()),
        )

    def stop(self) -> None:
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("FlowDesktop scheduler stopped")


async def _main(product_only: bool) -> None:
    await init_db()
    sched = FlowDesktopScheduler()
    if product_only:
        sched.start_product_only()
    else:
        sched.start()

    stop_event = asyncio.Event()

    def _handle_signal(signum, frame):
        logger.info("Received signal %s — shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        await stop_event.wait()
    finally:
        sched.stop()
        logger.info("FlowDesktop scheduler shutdown complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="FlowDesktop scheduler")
    parser.add_argument(
        "--product-only",
        action="store_true",
        help="Run only the product jobs (scheduled agents, simulator).",
    )
    args = parser.parse_args()
    asyncio.run(_main(product_only=args.product_only))


if __name__ == "__main__":
    main()
