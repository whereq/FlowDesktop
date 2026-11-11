"""Collect alternative data: SEC filings, insider Form 4, and short interest.

Sources (all keyless):

* SEC EDGAR — 10-K / 10-Q filings and insider Form 4 ownership transactions
* Yahoo Finance — short-interest snapshots

The SEC asks automated clients to identify themselves with a contact address.
Set ``SEC_USER_AGENT`` to something like ``Your Name you@example.com`` before
running this in production.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date

logger = logging.getLogger("flowdesk-collector.collectors.altdata")


async def collect_filings(session, symbols: list[str] | None = None, per_form: int = 1) -> dict:
    """Fetch the latest 10-K / 10-Q for each symbol.

    Returns ``{"fetched": n, "stored": m}``.
    """
    from sqlalchemy import select

    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_collector.providers.sec_edgar import SecEdgarProvider
    from flowdesk_collector.providers.sec_filings import fetch_latest_filings
    from flowdesk_core.models.company_filing import CompanyFiling

    if symbols is None:
        symbols = await active_symbols(session)
    if not symbols:
        return {"fetched": 0, "stored": 0}

    existing = {
        f.accession
        for f in (await session.execute(select(CompanyFiling.accession))).scalars().all()
    }

    edgar = SecEdgarProvider()
    stored = 0

    for sym in symbols:
        try:
            cik = await edgar.get_cik(sym)
        except Exception:
            logger.debug("CIK lookup failed for %s", sym, exc_info=True)
            continue
        if not cik:
            continue
        try:
            filings = await fetch_latest_filings(cik, per_form=per_form)
        except Exception:
            logger.debug("Filing fetch failed for %s", sym, exc_info=True)
            continue
        for f in filings:
            acc = f.get("accession")
            if not acc or acc in existing:
                continue
            session.add(
                CompanyFiling(
                    symbol=sym,
                    cik=cik,
                    form=f.get("form") or "",
                    filing_date=_pdate(f.get("filing_date")),
                    period_end=_pdate(f.get("period_end")),
                    accession=acc,
                    title=(f.get("title") or "")[:300] or None,
                    url=f.get("url"),
                    content=f.get("content") or "",
                )
            )
            existing.add(acc)
            stored += 1
        if stored:
            await session.commit()
        await asyncio.sleep(0.4)  # SEC rate limit: 10 requests/second max

    logger.info("Filings collected: %d stored", stored)
    return {"fetched": len(symbols), "stored": stored}


async def collect_insider_transactions(session, symbols: list[str] | None = None) -> dict:
    """Fetch recent insider Form 4 transactions for each symbol.

    Returns ``{"fetched": n, "stored": m}``.
    """
    from sqlalchemy import select

    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_collector.providers.sec_edgar import SecEdgarProvider
    from flowdesk_collector.providers.sec_insider import fetch_recent_form4
    from flowdesk_core.models.insider_transaction import InsiderTransaction

    if symbols is None:
        symbols = await active_symbols(session)
    if not symbols:
        return {"fetched": 0, "stored": 0}

    existing = {
        (a, li)
        for a, li in (
            await session.execute(
                select(InsiderTransaction.accession, InsiderTransaction.line_index)
            )
        )
        .tuples()
        .all()
    }

    edgar = SecEdgarProvider()
    stored = 0

    for sym in symbols:
        try:
            cik = await edgar.get_cik(sym)
        except Exception:
            continue
        if not cik:
            continue
        try:
            txns = await fetch_recent_form4(cik, max_filings=4)
        except Exception:
            logger.debug("Form 4 fetch failed for %s", sym, exc_info=True)
            continue
        for t in txns:
            key = (t.get("accession"), t.get("line_index"))
            if not key[0] or key in existing:
                continue
            session.add(
                InsiderTransaction(
                    symbol=sym,
                    cik=cik,
                    accession=t.get("accession"),
                    line_index=t.get("line_index") or 0,
                    filing_date=_pdate(t.get("filing_date")),
                    transaction_date=_pdate(t.get("transaction_date")),
                    insider_name=t.get("insider_name") or "Unknown",
                    insider_title=t.get("insider_title"),
                    is_director=bool(t.get("is_director")),
                    is_officer=bool(t.get("is_officer")),
                    is_ten_pct=bool(t.get("is_ten_pct")),
                    transaction_code=t.get("code"),
                    acquired_disposed=t.get("acquired_disposed"),
                    shares=t.get("shares"),
                    price=t.get("price"),
                    value=(t.get("shares") or 0) * (t.get("price") or 0) or None,
                    shares_owned_after=t.get("shares_after"),
                )
            )
            existing.add(key)
            stored += 1
        if stored:
            await session.commit()
        await asyncio.sleep(0.4)

    logger.info("Insider transactions collected: %d stored", stored)
    return {"fetched": len(symbols), "stored": stored}


async def collect_short_interest(session, symbols: list[str] | None = None) -> dict:
    """Fetch the latest short-interest snapshot for each symbol.

    Returns ``{"fetched": n, "stored": m}``.
    """
    from sqlalchemy import select

    from flowdesk_collector.collectors.universe import active_symbols
    from flowdesk_collector.providers.short_interest import fetch_short_interest
    from flowdesk_core.models.short_interest import ShortInterest

    if symbols is None:
        symbols = await active_symbols(session)
    if not symbols:
        return {"fetched": 0, "stored": 0}

    existing = {
        (s, d)
        for s, d in (
            await session.execute(select(ShortInterest.symbol, ShortInterest.settlement_date))
        )
        .tuples()
        .all()
    }

    stored = 0
    for sym in symbols:
        try:
            si = await fetch_short_interest(sym)
        except Exception:
            logger.debug("Short interest fetch failed for %s", sym, exc_info=True)
            continue
        if not si:
            continue
        shares = si.get("short_interest")
        if shares is None:
            continue  # the column is NOT NULL
        settlement = _pdate(si.get("settlement_date")) or date.today()
        if (sym, settlement) in existing:
            continue
        session.add(
            ShortInterest(
                symbol=sym,
                settlement_date=settlement,
                short_interest=int(shares),
                prior_short_interest=si.get("prior_short_interest"),
                avg_daily_volume=si.get("avg_daily_volume"),
                days_to_cover=si.get("days_to_cover"),
                short_pct_of_float=si.get("short_pct_of_float"),
                short_pct_of_outstanding=si.get("short_pct_of_outstanding"),
                change_pct=si.get("change_pct"),
                source="Yahoo Finance",
            )
        )
        existing.add((sym, settlement))
        stored += 1
        await asyncio.sleep(0.3)

    if stored:
        await session.commit()
    logger.info("Short interest collected: %d stored", stored)
    return {"fetched": len(symbols), "stored": stored}


def _pdate(value) -> date | None:
    """Coerce a provider date value into a ``date`` (or ``None``)."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            from datetime import datetime

            return datetime.strptime(s[:10] if "-" in s or "/" in s else s, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def sec_user_agent() -> str:
    """The User-Agent sent to SEC EDGAR. Override with ``SEC_USER_AGENT``."""
    return os.getenv("SEC_USER_AGENT", "FlowDesktop flowdesktop@example.com")
