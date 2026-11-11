"""System status and daily collection status API routes."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.auth import CurrentUser, get_current_user
from flowdesk_core.database import get_db
from flowdesk_core.models import (
    CrawlCoverage,
    CrawlerRunLog,
    HistoricalPrice,
    ProviderStatus,
    Quote,
    Stock,
)

router = APIRouter(prefix="/status", tags=["status"], dependencies=[Depends(get_current_user)])


def _require_admin(current_user: dict) -> None:
    """Raise 403 if the JWT does not carry the fd-admin realm role."""
    roles: list[str] = current_user.get("realm_access", {}).get("roles", [])
    if "fd-admin" not in roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )


@router.get("")
async def get_daily_status(
    ref_date: date = Query(default=None, description="Date to check (default: today)"),
    db: AsyncSession = Depends(get_db),
):
    """Get today's collection status summary.

    Returns:
    - Job runs: All scheduler jobs that ran today with their status
    - Provider stats: Per-provider throughput (symbols processed, records fetched)
    - Coverage: Quote coverage by exchange
    - Gaps: Symbols with failed or missing coverage
    """
    if ref_date is None:
        ref_date = date.today()

    # 1. Job runs summary
    runs_result = await db.execute(
        select(
            CrawlerRunLog.job_name,
            CrawlerRunLog.status,
            func.count(CrawlerRunLog.id).label("run_count"),
            func.sum(CrawlerRunLog.symbols_attempted).label("attempted"),
            func.sum(CrawlerRunLog.symbols_succeeded).label("succeeded"),
            func.sum(CrawlerRunLog.records_fetched).label("records"),
        )
        .where(CrawlerRunLog.plan_date == ref_date)
        .group_by(CrawlerRunLog.job_name, CrawlerRunLog.status)
        .order_by(CrawlerRunLog.job_name)
    )
    job_runs = [
        {
            "job": row.job_name,
            "status": row.status,
            "runs": row.run_count,
            "attempted": row.attempted or 0,
            "succeeded": row.succeeded or 0,
            "records": row.records or 0,
        }
        for row in runs_result.all()
    ]

    # 2. Provider stats
    provider_result = await db.execute(
        select(
            CrawlerRunLog.provider_name,
            func.sum(CrawlerRunLog.symbols_attempted).label("attempted"),
            func.sum(CrawlerRunLog.symbols_succeeded).label("succeeded"),
            func.sum(CrawlerRunLog.records_fetched).label("records"),
            func.max(CrawlerRunLog.ended_at).label("last_run"),
        )
        .where(CrawlerRunLog.plan_date == ref_date)
        .group_by(CrawlerRunLog.provider_name)
        .order_by(func.sum(CrawlerRunLog.records_fetched).desc())
    )
    providers = [
        {
            "provider": row.provider_name,
            "attempted": row.attempted or 0,
            "succeeded": row.succeeded or 0,
            "records": row.records or 0,
            "last_run": row.last_run.isoformat() if row.last_run else None,
        }
        for row in provider_result.all()
    ]

    # 3. Coverage by exchange
    coverage_result = await db.execute(
        select(
            Stock.exchange,
            func.count(Stock.id).label("total_stocks"),
        )
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    total_by_exchange = {row.exchange: row.total_stocks for row in coverage_result.all()}

    success_coverage_result = await db.execute(
        select(
            CrawlCoverage.provider,
            func.count(CrawlCoverage.id).label("count"),
        )
        .where(
            CrawlCoverage.coverage_date == ref_date,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status == "success",
        )
        .group_by(CrawlCoverage.provider)
    )
    covered_by_provider = {row.provider: row.count for row in success_coverage_result.all()}

    total_active = sum(total_by_exchange.values())
    total_covered = sum(covered_by_provider.values())

    # 4. Gap symbols (failed or no coverage)
    gap_result = await db.execute(
        select(
            CrawlCoverage.symbol,
            CrawlCoverage.status,
            CrawlCoverage.provider,
            CrawlCoverage.records_fetched,
        )
        .where(
            CrawlCoverage.coverage_date == ref_date,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status != "success",
        )
        .order_by(CrawlCoverage.symbol)
        .limit(20)
    )
    gaps = [
        {
            "symbol": row.symbol,
            "status": row.status,
            "provider": row.provider,
            "records": row.records_fetched,
        }
        for row in gap_result.all()
    ]

    # 5. Provider rate limits
    provider_status_result = await db.execute(
        select(ProviderStatus).order_by(ProviderStatus.priority)
    )
    rate_limits = [
        {
            "provider": s.provider_name,
            "daily_limit": s.daily_limit,
            "daily_used": s.daily_used,
            "daily_remaining": (s.daily_limit - s.daily_used) if s.daily_limit else None,
            "minute_limit": s.minute_limit,
            "minute_used": s.minute_used,
            "is_available": s.is_available,
        }
        for s in provider_status_result.scalars().all()
    ]

    return {
        "date": ref_date.isoformat(),
        "summary": {
            "total_active_stocks": total_active,
            "quotes_collected_today": total_covered,
            "coverage_rate": round(total_covered / total_active * 100, 1)
            if total_active > 0
            else None,
        },
        "job_runs": job_runs,
        "providers": providers,
        "rate_limits": rate_limits,
        "gaps": {
            "count": len(gaps),
            "samples": gaps,
        },
    }


@router.get("/providers")
async def get_provider_status(
    db: AsyncSession = Depends(get_db),
):
    """Get current rate-limit status for each data source."""
    result = await db.execute(select(ProviderStatus).order_by(ProviderStatus.priority))
    statuses = result.scalars().all()

    return {
        "providers": [
            {
                "name": s.provider_name,
                "priority": s.priority,
                "daily_limit": s.daily_limit,
                "daily_used": s.daily_used,
                "daily_remaining": (s.daily_limit - s.daily_used) if s.daily_limit else None,
                "minute_limit": s.minute_limit,
                "minute_used": s.minute_used,
                "is_available": s.is_available,
                "last_reset": s.last_reset.isoformat() if s.last_reset else None,
            }
            for s in statuses
        ]
    }


@router.get("/gaps")
async def get_coverage_gaps(
    days: int = Query(7, ge=1, le=30, description="Days to look back"),
    db: AsyncSession = Depends(get_db),
):
    """Get symbols with missing coverage over the past N days."""

    today = date.today()
    start_date = today - timedelta(days=days)

    # Get all active symbols
    stocks_result = await db.execute(
        select(Stock.symbol, Stock.name, Stock.exchange).where(Stock.is_active == True)  # noqa: E712
    )
    all_symbols = {
        row.symbol: {"name": row.name, "exchange": row.exchange} for row in stocks_result.all()
    }

    # Get symbols with successful quote coverage in the period
    covered_result = await db.execute(
        select(CrawlCoverage.symbol)
        .where(
            CrawlCoverage.coverage_date >= start_date,
            CrawlCoverage.coverage_date <= today,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status == "success",
            CrawlCoverage.records_fetched > 0,
        )
        .group_by(CrawlCoverage.symbol)
    )
    covered_symbols = {row.symbol for row in covered_result.all()}

    # Find gaps
    gap_symbols = set(all_symbols.keys()) - covered_symbols

    return {
        "period": f"{start_date.isoformat()} to {today.isoformat()}",
        "total_active_stocks": len(all_symbols),
        "stocks_with_coverage": len(covered_symbols),
        "stocks_with_gaps": len(gap_symbols),
        "gap_rate": round(len(gap_symbols) / len(all_symbols) * 100, 1) if all_symbols else 0,
        "symbols": [
            {"symbol": sym, "name": info["name"], "exchange": info["exchange"]}
            for sym, info in sorted(
                [(s, all_symbols[s]) for s in gap_symbols], key=lambda x: (x[1]["exchange"], x[0])
            )
        ][:100],  # Limit to 100 for response size
    }


@router.get("/summary")
async def get_status_summary(db: AsyncSession = Depends(get_db)):
    """Lightweight combined status payload for the System Status page.

    Returns db totals, per-exchange coverage for today, and today's job summary.
    """
    today = date.today()

    # --- DB totals ---

    stocks_count_result = await db.execute(
        select(func.count(Stock.id)).where(Stock.is_active == True)  # noqa: E712
    )
    stocks_count = stocks_count_result.scalar() or 0

    quotes_count_result = await db.execute(select(func.count(Quote.id)))
    quotes_count = quotes_count_result.scalar() or 0

    historical_count_result = await db.execute(select(func.count(HistoricalPrice.id)))
    historical_count = historical_count_result.scalar() or 0

    last_quote_result = await db.execute(select(func.max(Quote.timestamp)))
    last_quote_ts = last_quote_result.scalar()

    # --- Per-exchange coverage for today ---

    # Total active stocks per exchange
    exchange_totals_result = await db.execute(
        select(Stock.exchange, func.count(Stock.id).label("total"))
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    exchange_totals = {row.exchange: row.total for row in exchange_totals_result.all()}

    # Distinct symbols with a successful quote today, joined to stocks for exchange
    quoted_today_result = await db.execute(
        select(Stock.exchange, func.count(func.distinct(CrawlCoverage.symbol)).label("quoted"))
        .join(Stock, Stock.symbol == CrawlCoverage.symbol)
        .where(
            CrawlCoverage.coverage_date == today,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status == "success",
            Stock.is_active == True,  # noqa: E712
        )
        .group_by(Stock.exchange)
    )
    quoted_today = {row.exchange: row.quoted for row in quoted_today_result.all()}

    coverage = []
    for exchange, total in sorted(exchange_totals.items()):
        quoted = quoted_today.get(exchange, 0)
        pct = round(quoted / total * 100, 1) if total > 0 else 0.0
        coverage.append({"exchange": exchange, "total": total, "quoted_today": quoted, "pct": pct})

    # --- Jobs today: one row per job, best status, summed succeeded/attempted ---
    # "best status" ranks 'completed' above 'failed' — use a CASE to pick max rank per job.

    jobs_result = await db.execute(
        select(
            CrawlerRunLog.job_name,
            func.count(CrawlerRunLog.id).label("runs"),
            func.sum(CrawlerRunLog.symbols_succeeded).label("succeeded"),
            func.sum(CrawlerRunLog.symbols_attempted).label("attempted"),
            # Encode status priority as an integer so we can take the max
            func.max(
                case(
                    (CrawlerRunLog.status == "completed", 2),
                    (CrawlerRunLog.status == "ok", 1),
                    else_=0,
                )
            ).label("best_status_rank"),
        )
        .where(CrawlerRunLog.plan_date == today)
        .group_by(CrawlerRunLog.job_name)
        .order_by(CrawlerRunLog.job_name)
    )

    _rank_to_status = {2: "completed", 1: "ok", 0: "failed"}
    jobs_today = [
        {
            "job": row.job_name,
            "status": _rank_to_status.get(row.best_status_rank, "failed"),
            "runs": row.runs,
            "succeeded": row.succeeded or 0,
            "attempted": row.attempted or 0,
        }
        for row in jobs_result.all()
    ]

    return {
        "db": {
            "stocks": stocks_count,
            "quotes": quotes_count,
            "historical_records": historical_count,
            "last_quote": last_quote_ts.isoformat() if last_quote_ts else None,
        },
        "coverage": coverage,
        "jobs_today": jobs_today,
        "last_updated": datetime.now(UTC).isoformat(timespec="seconds"),
    }


@router.get("/admin")
async def get_admin_dashboard(
    ref_date: date = Query(default=None, description="Date to inspect (default: today)"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
):
    """Rich admin-only collector dashboard.

    Returns per-provider throughput, per-exchange coverage + data freshness,
    job run history, active blockers, and coverage gap breakdown.
    Requires the fd-admin Keycloak realm role.
    """
    _require_admin(current_user)

    if ref_date is None:
        ref_date = date.today()

    # ── 1. Summary totals ────────────────────────────────────────────────────
    stocks_total = (
        await db.execute(
            select(func.count(Stock.id)).where(Stock.is_active == True)  # noqa: E712
        )
    ).scalar() or 0

    quotes_total = (await db.execute(select(func.count(Quote.id)))).scalar() or 0

    historical_total = (await db.execute(select(func.count(HistoricalPrice.id)))).scalar() or 0

    last_quote_ts = (await db.execute(select(func.max(Quote.timestamp)))).scalar()

    quoted_today_total = (
        await db.execute(
            select(func.count(func.distinct(CrawlCoverage.symbol))).where(
                CrawlCoverage.coverage_date == ref_date,
                CrawlCoverage.data_type == "quote",
                CrawlCoverage.status == "success",
            )
        )
    ).scalar() or 0

    coverage_rate = round(quoted_today_total / stocks_total * 100, 1) if stocks_total else 0.0

    # ── 2. Per-provider throughput + quota ───────────────────────────────────
    prov_runs = await db.execute(
        select(
            CrawlerRunLog.provider_name,
            func.sum(CrawlerRunLog.symbols_attempted).label("attempted"),
            func.sum(CrawlerRunLog.symbols_succeeded).label("succeeded"),
            func.sum(CrawlerRunLog.records_fetched).label("records"),
            func.max(CrawlerRunLog.ended_at).label("last_run"),
            func.count(CrawlerRunLog.id).label("run_count"),
        )
        .where(CrawlerRunLog.plan_date == ref_date, CrawlerRunLog.provider_name.isnot(None))
        .group_by(CrawlerRunLog.provider_name)
        .order_by(func.sum(CrawlerRunLog.records_fetched).desc())
    )
    prov_run_map = {
        r.provider_name: {
            "attempted": r.attempted or 0,
            "succeeded": r.succeeded or 0,
            "records": r.records or 0,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "run_count": r.run_count,
        }
        for r in prov_runs.all()
    }

    quota_rows = await db.execute(select(ProviderStatus).order_by(ProviderStatus.priority))
    providers = []
    for s in quota_rows.scalars().all():
        run = prov_run_map.get(s.provider_name, {})
        att = run.get("attempted", 0)
        suc = run.get("succeeded", 0)
        providers.append(
            {
                "provider": s.provider_name,
                "priority": s.priority,
                "attempted": att,
                "succeeded": suc,
                "success_rate": round(suc / att * 100, 1) if att else None,
                "records": run.get("records", 0),
                "run_count": run.get("run_count", 0),
                "last_run": run.get("last_run"),
                "daily_limit": s.daily_limit,
                "daily_used": s.daily_used,
                "daily_remaining": (s.daily_limit - s.daily_used) if s.daily_limit else None,
                "minute_limit": s.minute_limit,
                "minute_used": s.minute_used,
                "is_available": s.is_available,
            }
        )

    # ── 3. Per-exchange coverage + data freshness ────────────────────────────
    ex_totals_rows = await db.execute(
        select(Stock.exchange, func.count(Stock.id).label("total"))
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    ex_totals = {r.exchange: r.total for r in ex_totals_rows.all()}

    ex_quoted_rows = await db.execute(
        select(Stock.exchange, func.count(func.distinct(CrawlCoverage.symbol)).label("quoted"))
        .join(Stock, Stock.symbol == CrawlCoverage.symbol)
        .where(
            CrawlCoverage.coverage_date == ref_date,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status == "success",
            Stock.is_active == True,  # noqa: E712
        )
        .group_by(Stock.exchange)
    )
    ex_quoted = {r.exchange: r.quoted for r in ex_quoted_rows.all()}

    # Latest historical_prices date per exchange (via stock join)
    ex_hist_rows = await db.execute(
        select(Stock.exchange, func.max(HistoricalPrice.date).label("latest_date"))
        .join(Stock, Stock.id == HistoricalPrice.stock_id)
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    ex_hist = {r.exchange: r.latest_date for r in ex_hist_rows.all()}

    exchanges = []
    for ex, total in sorted(ex_totals.items()):
        quoted = ex_quoted.get(ex, 0)
        latest_hist = ex_hist.get(ex)
        lag_days: int | None = None
        if latest_hist:
            lag_days = (ref_date - latest_hist).days
        exchanges.append(
            {
                "exchange": ex,
                "total": total,
                "quoted_today": quoted,
                "coverage_pct": round(quoted / total * 100, 1) if total else 0.0,
                "latest_historical_date": latest_hist.isoformat() if latest_hist else None,
                "data_lag_days": lag_days,
            }
        )

    # ── 4. Job runs today ────────────────────────────────────────────────────
    jobs_rows = await db.execute(
        select(
            CrawlerRunLog.job_name,
            func.count(CrawlerRunLog.id).label("runs"),
            func.sum(CrawlerRunLog.symbols_attempted).label("attempted"),
            func.sum(CrawlerRunLog.symbols_succeeded).label("succeeded"),
            func.sum(CrawlerRunLog.records_fetched).label("records"),
            func.max(CrawlerRunLog.ended_at).label("last_run"),
            func.max(
                case(
                    (CrawlerRunLog.status == "completed", 2),
                    (CrawlerRunLog.status == "ok", 1),
                    else_=0,
                )
            ).label("best_rank"),
        )
        .where(CrawlerRunLog.plan_date == ref_date)
        .group_by(CrawlerRunLog.job_name)
        .order_by(CrawlerRunLog.job_name)
    )
    _rank_map = {2: "completed", 1: "ok", 0: "failed"}
    jobs = [
        {
            "job": r.job_name,
            "status": _rank_map.get(r.best_rank, "failed"),
            "runs": r.runs,
            "attempted": r.attempted or 0,
            "succeeded": r.succeeded or 0,
            "records": r.records or 0,
            "last_run": r.last_run.isoformat() if r.last_run else None,
        }
        for r in jobs_rows.all()
    ]

    # ── 5. Blockers ──────────────────────────────────────────────────────────
    blockers = []
    for p in providers:
        if not p["is_available"]:
            blockers.append(
                {
                    "provider": p["provider"],
                    "type": "unavailable",
                    "message": f"{p['provider']} is marked unavailable",
                }
            )
        elif p["daily_limit"] and p["daily_remaining"] is not None and p["daily_remaining"] <= 0:
            blockers.append(
                {
                    "provider": p["provider"],
                    "type": "quota_exhausted",
                    "message": f"Daily quota exhausted ({p['daily_used']}/{p['daily_limit']})",
                }
            )

    # ── 6. Coverage gaps by exchange ─────────────────────────────────────────
    gaps_by_exchange: dict[str, int] = {}
    for ex_row in exchanges:
        gap = ex_row["total"] - ex_row["quoted_today"]
        if gap > 0:
            gaps_by_exchange[ex_row["exchange"]] = gap

    return {
        "date": ref_date.isoformat(),
        "summary": {
            "total_active_stocks": stocks_total,
            "total_quotes_db": quotes_total,
            "total_historical_db": historical_total,
            "quoted_today": quoted_today_total,
            "coverage_rate": coverage_rate,
            "last_activity": last_quote_ts.isoformat() if last_quote_ts else None,
        },
        "providers": providers,
        "exchanges": exchanges,
        "jobs": jobs,
        "blockers": blockers,
        "gaps": {
            "total_missing": sum(gaps_by_exchange.values()),
            "by_exchange": gaps_by_exchange,
        },
        "last_updated": datetime.now(UTC).isoformat(timespec="seconds"),
    }


@router.get("/history")
async def get_coverage_history(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    exchange: str = Query(default=None, description="Filter by exchange code"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
):
    """Per-exchange coverage history over a date range (admin only)."""
    _require_admin(current_user)

    if (end_date - start_date).days > 90:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail="Date range cannot exceed 90 days"
        )

    # Total active stocks per exchange (static denominator)
    ex_totals_result = await db.execute(
        select(Stock.exchange, func.count(Stock.id).label("total"))
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    ex_totals = {r.exchange: r.total for r in ex_totals_result.all()}

    # Daily quoted counts per exchange
    coverage_q = (
        select(
            Stock.exchange,
            CrawlCoverage.coverage_date,
            func.count(func.distinct(CrawlCoverage.symbol)).label("quoted"),
        )
        .join(Stock, Stock.symbol == CrawlCoverage.symbol)
        .where(
            CrawlCoverage.coverage_date >= start_date,
            CrawlCoverage.coverage_date <= end_date,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status == "success",
            Stock.is_active == True,  # noqa: E712
        )
        .group_by(Stock.exchange, CrawlCoverage.coverage_date)
        .order_by(CrawlCoverage.coverage_date, Stock.exchange)
    )
    if exchange:
        coverage_q = coverage_q.where(Stock.exchange == exchange)

    rows = await db.execute(coverage_q)

    data = []
    for r in rows.all():
        total = ex_totals.get(r.exchange, 0)
        pct = round(r.quoted / total * 100, 1) if total else 0.0
        data.append(
            {
                "date": r.coverage_date.isoformat(),
                "exchange": r.exchange,
                "quoted": r.quoted,
                "total": total,
                "coverage_pct": pct,
            }
        )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "exchanges": list(ex_totals.keys()),
        "data": data,
    }


@router.get("/anomalies")
async def get_anomalies(
    lookback_days: int = Query(default=7, ge=3, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
):
    """Detect potential collector issues over the past N days (admin only).

    Checks:
    - Exchanges with zero quote coverage for 2+ consecutive past days
    - Exchanges with historical data lag >= 3 days
    - Providers with daily quota exhausted
    - Exchanges with sudden coverage drop (>= 40 pct-point decline vs prior day)
    """
    _require_admin(current_user)

    today = date.today()
    start = today - timedelta(days=lookback_days)

    # --- Exchange totals ---
    ex_totals_result = await db.execute(
        select(Stock.exchange, func.count(Stock.id).label("total"))
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    ex_totals = {r.exchange: r.total for r in ex_totals_result.all()}

    # --- Per-exchange, per-day coverage ---
    cov_result = await db.execute(
        select(
            Stock.exchange,
            CrawlCoverage.coverage_date,
            func.count(func.distinct(CrawlCoverage.symbol)).label("quoted"),
        )
        .join(Stock, Stock.symbol == CrawlCoverage.symbol)
        .where(
            CrawlCoverage.coverage_date >= start,
            CrawlCoverage.coverage_date <= today,
            CrawlCoverage.data_type == "quote",
            CrawlCoverage.status == "success",
            Stock.is_active == True,  # noqa: E712
        )
        .group_by(Stock.exchange, CrawlCoverage.coverage_date)
    )
    # timeline[exchange][date] = quoted_count
    timeline: dict[str, dict] = {}
    for r in cov_result.all():
        timeline.setdefault(r.exchange, {})[r.coverage_date] = r.quoted

    # --- Historical lag per exchange ---
    hist_result = await db.execute(
        select(Stock.exchange, func.max(HistoricalPrice.date).label("latest"))
        .join(Stock, Stock.id == HistoricalPrice.stock_id)
        .where(Stock.is_active == True)  # noqa: E712
        .group_by(Stock.exchange)
    )
    hist_latest = {r.exchange: r.latest for r in hist_result.all()}

    # --- Provider quota status ---
    prov_result = await db.execute(select(ProviderStatus))
    providers = {p.provider_name: p for p in prov_result.scalars().all()}

    anomalies = []

    for ex, total in ex_totals.items():
        if total == 0:
            continue

        ex_timeline = timeline.get(ex, {})

        # Check consecutive zero-coverage past days (skip today — still collecting)
        zero_streak = 0
        zero_dates = []
        for i in range(1, lookback_days + 1):
            check = today - timedelta(days=i)
            if ex_timeline.get(check, 0) == 0:
                zero_streak += 1
                zero_dates.append(check.isoformat())
            else:
                break  # streak broken

        if zero_streak >= 2:
            # For exchanges where historical_prices IS current, the streak is a
            # live-quote collection gap (collector missed market hours), not a
            # true data outage.  Downgrade severity and clarify the message.
            hist_lag = (today - hist_latest[ex]).days if hist_latest.get(ex) else 999
            historical_ok = hist_lag <= 1  # yesterday or today covered
            if historical_ok:
                severity = "warning"
                title = (
                    f"{ex}: {zero_streak}d without live quotes "
                    f"(historical prices current — collector missed market window)"
                )
                detail = (
                    f"No live quotes: {', '.join(zero_dates)}. "
                    f"Historical prices up to date (lag {hist_lag}d). "
                    f"Likely cause: collector restarted after market close. "
                    f"Fix: avoid restarting the collector container between 01:30–07:00 UTC."
                )
            else:
                severity = "critical" if zero_streak >= 3 else "warning"
                title = f"{ex}: {zero_streak} consecutive days with no quotes"
                detail = f"Missing: {', '.join(zero_dates)}"
            anomalies.append(
                {
                    "type": "zero_coverage_streak",
                    "severity": severity,
                    "exchange": ex,
                    "provider": None,
                    "title": title,
                    "detail": detail,
                }
            )

        # Sudden drop: yesterday vs day-before-yesterday (skip if yesterday zero already caught above)
        if zero_streak < 2:
            yesterday = today - timedelta(days=1)
            day_before = today - timedelta(days=2)
            quoted_yesterday = ex_timeline.get(yesterday, 0)
            quoted_before = ex_timeline.get(day_before, 0)
            pct_yesterday = quoted_yesterday / total * 100 if total else 0
            pct_before = quoted_before / total * 100 if total else 0
            if pct_before >= 40 and pct_yesterday < (pct_before - 40):
                anomalies.append(
                    {
                        "type": "sudden_drop",
                        "severity": "warning",
                        "exchange": ex,
                        "provider": None,
                        "title": f"{ex}: coverage dropped {pct_before:.0f}% → {pct_yesterday:.0f}% yesterday",
                        "detail": f"{quoted_before:,} → {quoted_yesterday:,} symbols quoted",
                    }
                )

        # Historical data lag
        latest = hist_latest.get(ex)
        if latest:
            lag = (today - latest).days
            if lag >= 3:
                anomalies.append(
                    {
                        "type": "data_lag",
                        "severity": "critical" if lag >= 7 else "warning",
                        "exchange": ex,
                        "provider": None,
                        "title": f"{ex}: historical data is {lag} days behind",
                        "detail": f"Latest record date: {latest.isoformat()}",
                    }
                )

    # Provider quota exhausted
    for pname, p in providers.items():
        if p.daily_limit and p.daily_used >= p.daily_limit:
            anomalies.append(
                {
                    "type": "quota_exhausted",
                    "severity": "warning",
                    "exchange": None,
                    "provider": pname,
                    "title": f"{pname}: daily quota exhausted ({p.daily_used}/{p.daily_limit})",
                    "detail": "Quota resets at midnight UTC",
                }
            )
        if not p.is_available:
            # Distinguish "never configured" (no API key set, daily_used=0)
            # from "circuit breaker tripped" (was working, then failed).
            # A provider that tripped the breaker will have daily_used > 0
            # or will have had recent successful crawl coverage.
            never_used = p.daily_used == 0
            if never_used:
                severity = "info"
                title = f"{pname}: not configured (no API key)"
                detail = (
                    "Provider has never been used. "
                    "Set the required API key/token in .env to enable it, "
                    "or ignore if this provider is intentionally disabled."
                )
            else:
                severity = "critical"
                title = f"{pname}: marked unavailable"
                detail = (
                    f"Provider was active today ({p.daily_used} calls) but is now unavailable. "
                    "Circuit breaker may be open — check collector logs."
                )
            anomalies.append(
                {
                    "type": "provider_down",
                    "severity": severity,
                    "exchange": None,
                    "provider": pname,
                    "title": title,
                    "detail": detail,
                }
            )

    # Sort: critical first
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    anomalies.sort(key=lambda a: severity_order.get(a["severity"], 3))

    return {
        "lookback_days": lookback_days,
        "anomaly_count": len(anomalies),
        "critical_count": sum(1 for a in anomalies if a["severity"] == "critical"),
        "warning_count": sum(1 for a in anomalies if a["severity"] == "warning"),
        "anomalies": anomalies,
        "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
