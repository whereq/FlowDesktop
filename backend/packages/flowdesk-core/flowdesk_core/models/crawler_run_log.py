"""Crawler run log — per-provider-per-job-run statistics."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base


class CrawlerRunLog(Base):
    """Records timing and throughput statistics for every crawler job run.

    One record is written per provider per scheduler-job invocation.
    A single job (e.g. collect_realtime_quotes) may produce multiple rows when
    it uses several providers across different exchanges.

    The run_id UUID ties all provider sub-rows belonging to the same invocation.

    Joined with provider_registry for quota context and provider_status for
    live rate-limit counters, this table drives the daily statistics report.
    """

    __tablename__ = "crawler_run_log"
    __table_args__ = (
        Index("idx_run_log_provider_date", "provider_name", "plan_date"),
        Index("idx_run_log_job_started", "job_name", "started_at"),
        Index("idx_run_log_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # UUID that groups all provider rows produced by one scheduler-job call
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Scheduler job that triggered this run
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "collect_realtime_quotes", "collect_historical_backfill",
    #      "collect_eod_us_bulk", "collect_enrichment_data"

    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(20))
    # Exchange context for this run (NULL when provider covers all exchanges)

    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "quote" | "historical" | "eod_bulk" | "info" | "fundamental" | "macro"

    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    # Symbol-level counts
    symbols_attempted: Mapped[int] = mapped_column(Integer, default=0)
    symbols_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    symbols_failed: Mapped[int] = mapped_column(Integer, default=0)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)

    # Quota snapshot — snapshot at the moment this run started/ended
    daily_quota_limit: Mapped[int | None] = mapped_column(Integer)
    # NULL means unlimited
    daily_quota_before: Mapped[int] = mapped_column(Integer, default=0)
    daily_quota_after: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(20), default="running")
    # "running" | "completed" | "partial" | "failed" | "skipped"

    error_summary: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return (
            f"<CrawlerRunLog {self.provider_name}/{self.data_type}"
            f" @ {self.plan_date} [{self.status}]"
            f" records={self.records_fetched} dur={self.duration_seconds}s>"
        )
