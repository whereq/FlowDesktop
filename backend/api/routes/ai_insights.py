"""AI Insights endpoints — chart narration, morning brief, and future AI features.

All endpoints use the platform LLM provider (no BYOK needed — these are
server-driven analyses, not user chat). Quota is shared with the chat endpoint.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.llm_gateway import LLMGateway, provider_api_base, resolve_platform_provider
from api.services.skills import get_skill, run_skill
from api.services.stock_context_builder import (
    build_comparison_context,
    build_macro_impact_context,
    build_morning_brief_context,
    build_portfolio_context,
    build_stock_context,
    render_committee_prompt,
    render_comparison_prompt,
    render_macro_impact_prompt,
    render_morning_brief_prompt,
    render_portfolio_analysis_prompt,
    render_stock_analysis_prompt,
    run_stock_screen,
    run_strategy_backtest,
)
from flowdesk_core.auth import CurrentUser
from flowdesk_core.database import get_db
from flowdesk_core.models.chat_quota import ADMIN_ROLE, PAID_ROLES, ChatQuota

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai-insights"])


class AILocaleBody(BaseModel):
    locale: str = "en"


_gateway = LLMGateway()


def _extract_roles(user: dict) -> list[str]:
    realm = user.get("realm_access") or {}
    return realm.get("roles") or []


async def _suggest_symbols(db: AsyncSession, query: str, limit: int = 5) -> list[dict]:
    """Return symbols similar to `query` for typo-tolerant error messages.

    Strategy (in order):
      1. Exact prefix — e.g., "SNY" → nothing; "SNAP" → SNAP
      2. Truncated prefix — handles insertion typos: "TSLAA" → TSLA% (drop last char)
      3. Contains match — looser
      4. Name match — user typed a company name (e.g., "apple")
    Results are de-duplicated and ordered by closest match first.
    """
    from sqlalchemy import select as sa_select

    from flowdesk_core.models import Stock

    q = (query or "").upper().strip()
    if not q:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    def _add(rows) -> None:
        for s in rows:
            if s.symbol in seen:
                continue
            seen.add(s.symbol)
            results.append({"symbol": s.symbol, "name": s.name, "exchange": s.exchange})

    async def _select_prefix(prefix: str) -> None:
        rows = (
            await db.execute(
                sa_select(Stock.symbol, Stock.name, Stock.exchange)
                .where(Stock.is_active == True, Stock.symbol.ilike(f"{prefix}%"))  # noqa: E712
                .order_by(Stock.symbol)
                .limit(limit)
            )
        ).all()
        _add(rows)

    # 1. Exact prefix
    await _select_prefix(q)

    # 2. Truncated prefixes — handle insertion typos like TSLAA→TSLA, AAPLL→AAPL
    # Trim 1-2 chars from the right until we get a hit (or the prefix is too short).
    for trim in (1, 2):
        if len(results) >= limit or len(q) - trim < 2:
            break
        await _select_prefix(q[:-trim])

    # 3. Contains match — looser (substring of symbol)
    if len(results) < limit and len(q) >= 2:
        rows = (
            await db.execute(
                sa_select(Stock.symbol, Stock.name, Stock.exchange)
                .where(Stock.is_active == True, Stock.symbol.ilike(f"%{q}%"))  # noqa: E712
                .order_by(Stock.symbol)
                .limit(limit)
            )
        ).all()
        _add(rows)

    # 4. Name match — user typed a company name (e.g., "apple", "nvidia")
    if len(results) < limit and len(q) >= 3:
        rows = (
            await db.execute(
                sa_select(Stock.symbol, Stock.name, Stock.exchange)
                .where(Stock.is_active == True, Stock.name.ilike(f"%{q}%"))  # noqa: E712
                .order_by(Stock.name)
                .limit(limit)
            )
        ).all()
        _add(rows)

    return results[:limit]


def _symbol_not_found_detail(symbol: str, suggestions: list[dict]) -> dict:
    """Structured 404 body for an unknown symbol, with a 'did you mean' list."""
    msg = f"Symbol '{symbol}' is not in the FlowDesktop stock universe."
    if suggestions:
        rendered = ", ".join(f"{s['symbol']} ({s['name']})" for s in suggestions[:3])
        msg += f" Did you mean: {rendered}?"
    else:
        msg += " Only symbols in our collected universe can be analyzed."
    return {
        "code": "symbol_not_found",
        "message": msg,
        "query": symbol,
        "suggestions": suggestions,
    }


async def _check_quota(db: AsyncSession, user_id: UUID, roles: list[str]) -> None:
    """Raise 402 if user's free trial is exhausted. Admins and paid tiers bypass."""
    if ADMIN_ROLE in roles or any(r in roles for r in PAID_ROLES):
        return
    from datetime import datetime, timedelta

    from sqlalchemy import select as sa_select

    from flowdesk_core.models.chat_quota import FREE_TRIAL_DAYS, FREE_TRIAL_MESSAGE_LIMIT

    result = await db.execute(sa_select(ChatQuota).where(ChatQuota.keycloak_id == user_id))
    quota = result.scalar_one_or_none()
    if quota is None:
        return  # no usage yet — allow

    now = datetime.now(UTC)
    trial_expired = (now - quota.trial_start.replace(tzinfo=UTC)) > timedelta(days=FREE_TRIAL_DAYS)
    msg_exhausted = quota.messages_used >= FREE_TRIAL_MESSAGE_LIMIT
    if trial_expired or msg_exhausted:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Free trial exhausted. Please upgrade to continue using FlowDesktop AI.",
        )


# ---------------------------------------------------------------------------
# POST /ai/analyze/{symbol} — streaming chart narration
# ---------------------------------------------------------------------------


@router.post("/analyze/{symbol}")
async def analyze_stock(
    symbol: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    body: AILocaleBody = Body(default_factory=AILocaleBody),
):
    """Stream an AI analysis of a stock using FlowDesktop's collected data.

    Builds context from historical_prices, quotes, stocks, and fundamental_data
    tables, then streams a structured analysis back to the client.
    """
    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    ctx = await build_stock_context(db, symbol.upper())
    if ctx is None:
        suggestions = await _suggest_symbols(db, symbol.upper())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_symbol_not_found_detail(symbol.upper(), suggestions),
        )

    # Run via the Research Analyst skill: scoped tool subset (~7 vs 22), focused
    # persona prompt, and the heavy reasoning tier. The pre-rendered context
    # prompt is the user message; the skill can fetch any missing pieces.
    skill = get_skill("research_analyst")
    prompt = render_stock_analysis_prompt(ctx, locale=body.locale)

    async def _stream():
        try:
            async for chunk in run_skill(
                skill,
                db=db,
                user_id=str(user_id),
                user_text=prompt,
                symbols=[symbol.upper()],
                locale=body.locale,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("AI analysis stream error for %s: %s", symbol, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Analysis failed. Please try again.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /ai/analyze/{symbol}/context — non-streaming context preview (debug/dev)
# ---------------------------------------------------------------------------


@router.get("/analyze/{symbol}/context")
async def get_stock_context(
    symbol: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return the raw context dict that would be sent to the LLM for a symbol.
    Useful for debugging and frontend preview cards.
    """
    ctx = await build_stock_context(db, symbol.upper())
    if ctx is None:
        suggestions = await _suggest_symbols(db, symbol.upper())
        raise HTTPException(
            status_code=404, detail=_symbol_not_found_detail(symbol.upper(), suggestions)
        )
    return ctx


# ---------------------------------------------------------------------------
# POST /ai/brief — streaming morning brief for the user's watchlist
# ---------------------------------------------------------------------------


@router.post("/brief")
async def morning_brief(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    body: AILocaleBody = Body(default_factory=AILocaleBody),
):
    """Stream a morning brief summarising the user's watchlist and macro indicators.

    Pulls watchlist symbols from the user_watchlists table, then assembles
    latest quotes + FRED macro data into a concise daily brief.
    """
    from flowdesk_core.models.watchlist import WatchlistItem

    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # Fetch watchlist
    from sqlalchemy import select as sa_select

    wl_result = await db.execute(
        sa_select(WatchlistItem).where(WatchlistItem.keycloak_id == str(user_id))
    )
    watchlist_rows = wl_result.scalars().all()
    symbols = [row.symbol for row in watchlist_rows]

    ctx = await build_morning_brief_context(db, symbols)
    if not ctx["has_data"] and not ctx["macro"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "no_data",
                "message": (
                    "Your watchlist is empty, so there is nothing to summarize. "
                    "Add at least one stock to your watchlist to receive a morning brief. "
                    f"You have {len(symbols)} watchlist item(s) currently."
                ),
                "watchlist_count": len(symbols),
            },
        )

    prompt = render_morning_brief_prompt(ctx)
    messages = [{"role": "user", "content": prompt}]

    async def _stream():
        try:
            async for chunk in _gateway.stream_chat(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                messages=messages,
                db=db,
                user_id=str(user_id),
                symbols=symbols,
                temperature=0.5,
                max_tokens=512,
                locale=body.locale,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("Morning brief stream error for user %s: %s", user_id, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Brief generation failed.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /ai/screen — natural language stock screener
# ---------------------------------------------------------------------------


class ScreenRequest(BaseModel):
    query: str


@router.post("/screen")
async def screen_stocks(
    body: ScreenRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Parse a natural-language query into filters and screen the stocks DB."""
    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    extraction_prompt = (
        "Extract stock screening filters from this query as JSON. Output ONLY valid JSON, nothing else.\n"
        'Schema: {"exchanges": list of exchange codes from [NYSE,NASDAQ,TSX,SSE,SZSE,HK,JPX,SGX,TAI,KSC] or null, '
        '"sectors": list of sector strings or null, "market_cap_min": number in USD or null, '
        '"market_cap_max": number or null, "price_min": number or null, "price_max": number or null, '
        '"change_pct_min": number or null, "change_pct_max": number or null, "limit": number default 20}\n'
        f"Query: {body.query}"
    )

    messages = [{"role": "user", "content": extraction_prompt}]
    raw_json = ""
    try:
        async for chunk in _gateway.stream_chat(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            messages=messages,
            db=db,
            user_id=str(user_id),
            symbols=[],
            temperature=0.0,
            max_tokens=200,
        ):
            if isinstance(chunk, dict) and "delta" in chunk:
                raw_json += chunk["delta"]
    except Exception as exc:
        logger.error("Screen filter extraction failed: %s", exc)
        raise HTTPException(status_code=500, detail="Filter extraction failed.")

    filters: dict = {}
    try:
        start = raw_json.find("{")
        end = raw_json.rfind("}") + 1
        if start != -1 and end > start:
            filters = json.loads(raw_json[start:end])
    except Exception:
        filters = {}

    results = await run_stock_screen(db, filters)
    return {"query": body.query, "filters": filters, "results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# POST /ai/compare — head-to-head stock comparison (streaming)
# ---------------------------------------------------------------------------


class CompareRequest(BaseModel):
    symbols: list[str]
    locale: str = "en"


@router.post("/compare")
async def compare_stocks(
    body: CompareRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Stream a head-to-head comparison of 2-3 stocks."""
    if len(body.symbols) < 2 or len(body.symbols) > 3:
        raise HTTPException(status_code=400, detail="Provide 2 or 3 symbols for comparison.")

    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    ctx = await build_comparison_context(db, body.symbols)
    if not ctx["stocks"]:
        # Build per-symbol suggestions for any that weren't found
        found = {s.get("symbol") for s in ctx.get("stocks", [])}
        missing = [s for s in body.symbols if s.upper() not in {f.upper() for f in found}]
        per_sym: dict[str, list[dict]] = {}
        for sym in missing:
            per_sym[sym.upper()] = await _suggest_symbols(db, sym.upper(), limit=3)
        msg = "None of the provided symbols are in the FlowDesktop stock universe."
        msg_suggestions: list[str] = []
        for sym in missing:
            suggs = per_sym.get(sym.upper(), [])
            if suggs:
                msg_suggestions.append(
                    f"{sym.upper()} → did you mean {', '.join(s['symbol'] for s in suggs)}?"
                )
        if msg_suggestions:
            msg += " " + " ".join(msg_suggestions)
        raise HTTPException(
            status_code=404,
            detail={
                "code": "symbols_not_found",
                "message": msg,
                "missing": missing,
                "suggestions": per_sym,
            },
        )

    prompt = render_comparison_prompt(ctx, locale=body.locale)
    symbols_upper = [s.upper() for s in body.symbols]
    skill = get_skill("stock_comparator")  # scoped tools + heavy tier

    async def _stream_compare():
        try:
            async for chunk in run_skill(
                skill,
                db=db,
                user_id=str(user_id),
                user_text=prompt,
                symbols=symbols_upper,
                locale=body.locale,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("Compare stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Comparison failed.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_compare(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /ai/macro-impact — macro event impact on watchlist (streaming)
# ---------------------------------------------------------------------------


class MacroImpactRequest(BaseModel):
    event: str
    locale: str = "en"


@router.post("/macro-impact")
async def macro_impact(
    body: MacroImpactRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Stream macro event impact analysis for the user's watchlist."""
    from sqlalchemy import select as sa_select

    from flowdesk_core.models.watchlist import WatchlistItem

    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    wl_result = await db.execute(
        sa_select(WatchlistItem).where(WatchlistItem.keycloak_id == str(user_id))
    )
    symbols = [row.symbol for row in wl_result.scalars().all()]

    ctx = await build_macro_impact_context(db, body.event, symbols)
    if not ctx.get("has_data") and not ctx.get("macro"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "no_data",
                "message": (
                    "Your watchlist is empty, so there is nothing to analyze. "
                    "Add at least one stock to your watchlist before running a macro impact analysis. "
                    f"You have {len(symbols)} watchlist item(s) currently."
                ),
                "watchlist_count": len(symbols),
            },
        )

    prompt = render_macro_impact_prompt(ctx, body.event, locale=body.locale)
    messages = [{"role": "user", "content": prompt}]

    async def _stream_macro():
        try:
            async for chunk in _gateway.stream_chat(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                messages=messages,
                db=db,
                user_id=str(user_id),
                symbols=symbols,
                temperature=0.5,
                max_tokens=600,
                locale=body.locale,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("Macro impact stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Macro impact analysis failed.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_macro(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /ai/committee/{symbol} — investment committee (3 sequential agents)
# ---------------------------------------------------------------------------


@router.post("/committee/{symbol}")
async def investment_committee(
    symbol: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    body: AILocaleBody = Body(default_factory=AILocaleBody),
):
    """Stream a 3-role investment committee debate: bull, bear, risk."""
    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    ctx = await build_stock_context(db, symbol.upper())
    if ctx is None:
        suggestions = await _suggest_symbols(db, symbol.upper())
        raise HTTPException(
            status_code=404, detail=_symbol_not_found_detail(symbol.upper(), suggestions)
        )

    _zh = body.locale.startswith("zh")
    committee_roles = [
        ("bull", f"### {'多方论点' if _zh else 'Bull Case'}\n\n"),
        ("bear", f"### {'空方论点' if _zh else 'Bear Case'}\n\n"),
        ("risk", f"### {'风险评估' if _zh else 'Risk Assessment'}\n\n"),
    ]

    async def _stream_committee():
        try:
            for role, header in committee_roles:
                yield f"data: {json.dumps({'delta': header})}\n\n"
                prompt = render_committee_prompt(ctx, role, locale=body.locale)
                msgs = [{"role": "user", "content": prompt}]
                async for chunk in _gateway.stream_chat(
                    provider_name=provider_name,
                    model=model,
                    api_key=api_key,
                    messages=msgs,
                    db=db,
                    user_id=str(user_id),
                    symbols=[symbol.upper()],
                    temperature=0.6,
                    max_tokens=200,
                    locale=body.locale,
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield f"data: {json.dumps({'delta': chr(10) + chr(10) + '---' + chr(10) + chr(10)})}\n\n"
        except Exception as exc:
            logger.error("Committee stream error for %s: %s", symbol, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Committee analysis failed.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_committee(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# POST /ai/strategy — strategy builder + backtest
# ---------------------------------------------------------------------------


class StrategyRequest(BaseModel):
    symbol: str
    strategy: str
    locale: str = "en"


@router.post("/strategy")
async def strategy_builder(
    body: StrategyRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Extract rules from a strategy description, backtest, and stream results."""
    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    extraction_prompt = (
        "Extract trading strategy rules as JSON from this description. Output ONLY valid JSON.\n"
        'Schema: {"entry_condition": one of ["rsi_below","consecutive_down_days","price_below_ma"], '
        '"entry_threshold": number, "exit_days": integer (default 10), "notes": string}\n'
        f"Strategy: {body.strategy}"
    )
    raw_rules = ""
    try:
        async for chunk in _gateway.stream_chat(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            messages=[{"role": "user", "content": extraction_prompt}],
            db=db,
            user_id=str(user_id),
            symbols=[body.symbol.upper()],
            temperature=0.0,
            max_tokens=150,
            api_base=provider_api_base(provider_name),
            tool_names=[],  # pure JSON extraction — no tools needed
        ):
            if isinstance(chunk, dict) and "delta" in chunk:
                raw_rules += chunk["delta"]
    except Exception as exc:
        logger.error("Strategy rule extraction failed: %s", exc)

    rules: dict = {}
    try:
        start = raw_rules.find("{")
        end = raw_rules.rfind("}") + 1
        if start != -1 and end > start:
            rules = json.loads(raw_rules[start:end])
    except Exception:
        rules = {"entry_condition": "rsi_below", "entry_threshold": 30, "exit_days": 10}

    backtest = await run_strategy_backtest(db, body.symbol, rules)

    entry_label = rules.get("entry_condition", "rsi_below").replace("_", " ")
    threshold = rules.get("entry_threshold", 30)
    exit_d = int(rules.get("exit_days", 10))
    notes = rules.get("notes", "")
    bt = backtest

    narrative_prompt = (
        f"You are FlowDesktop AI presenting a strategy backtest result for {body.symbol.upper()}.\n\n"
        f"Strategy description: {body.strategy}\n"
        f"Formalized rules: entry when {entry_label} crosses {threshold}, "
        f"exit after {exit_d} trading days. {notes}\n\n"
        f"Backtest results ({bt.get('data_points', '?')} data points, up to 2 years):\n"
        f"Trades: {bt.get('num_trades', 0)} | "
        f"Win rate: {bt.get('win_rate', 'N/A')}% | "
        f"Avg return: {bt.get('avg_return_pct', 'N/A')}% | "
        f"Worst trade: {bt.get('max_drawdown_pct', 'N/A')}% | "
        f"Avg hold: {bt.get('avg_hold_days', exit_d)} days\n\n"
        "Write a 150-200 word narrative covering:\n"
        "1. The formalized strategy rules in plain English\n"
        "2. What the backtest numbers show\n"
        "3. One key limitation of this simple backtest\n"
        "Be factual. No buy/sell recommendations."
    )

    async def _stream_strategy():
        table = (
            f"**Backtest Results** ({body.symbol.upper()})\n\n"
            f"| Metric | Value |\n|--------|-------|\n"
            f"| Trades | {bt.get('num_trades', 0)} |\n"
            f"| Win Rate | {bt.get('win_rate', 'N/A')}% |\n"
            f"| Avg Return | {bt.get('avg_return_pct', 'N/A')}% |\n"
            f"| Worst Trade | {bt.get('max_drawdown_pct', 'N/A')}% |\n"
            f"| Avg Hold | {bt.get('avg_hold_days', exit_d)} days |\n\n"
        )
        yield f"data: {json.dumps({'delta': table})}\n\n"
        try:
            async for chunk in _gateway.stream_chat(
                provider_name=provider_name,
                model=model,
                api_key=api_key,
                messages=[{"role": "user", "content": narrative_prompt}],
                db=db,
                user_id=str(user_id),
                symbols=[body.symbol.upper()],
                temperature=0.4,
                max_tokens=300,
                locale=body.locale,
                api_base=provider_api_base(provider_name),
                allow_routing=True,
                force_tier="heavy",  # better prose for the backtest narrative
                tool_names=[],  # narrative is self-contained — no tools
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("Strategy stream error for %s: %s", body.symbol, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Strategy analysis failed.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_strategy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Shadow Portfolio endpoints
# ---------------------------------------------------------------------------


class TradeIn(BaseModel):
    symbol: str
    action: str
    shares: float
    price: float
    note: str | None = None
    trade_date: str | None = None


@router.post("/portfolio/trades", status_code=201)
async def add_shadow_trade(
    body: TradeIn,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Record a paper trade in the user's shadow portfolio."""
    from decimal import Decimal

    from flowdesk_core.models.shadow_portfolio import ShadowTrade

    user_id = UUID(current_user["sub"])
    trade_date = datetime.utcnow()
    if body.trade_date:
        try:
            trade_date = datetime.fromisoformat(body.trade_date)
        except ValueError:
            pass

    trade = ShadowTrade(
        keycloak_id=user_id,
        symbol=body.symbol.upper(),
        action=body.action.lower(),
        shares=Decimal(str(body.shares)),
        price=Decimal(str(body.price)),
        note=body.note,
        trade_date=trade_date,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)

    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "action": trade.action,
        "shares": float(trade.shares),
        "price": float(trade.price),
        "note": trade.note,
        "trade_date": trade.trade_date.isoformat(),
        "created_at": trade.created_at.isoformat(),
    }


@router.get("/portfolio/trades")
async def list_shadow_trades(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """List all paper trades for the authenticated user."""
    from sqlalchemy import select as sa_select

    from flowdesk_core.models.shadow_portfolio import ShadowTrade

    user_id = UUID(current_user["sub"])
    result = await db.execute(
        sa_select(ShadowTrade)
        .where(ShadowTrade.keycloak_id == user_id)
        .order_by(ShadowTrade.trade_date.desc())
    )
    trades = result.scalars().all()
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "action": t.action,
            "shares": float(t.shares),
            "price": float(t.price),
            "note": t.note,
            "trade_date": t.trade_date.isoformat(),
            "created_at": t.created_at.isoformat(),
        }
        for t in trades
    ]


@router.delete("/portfolio/trades/{trade_id}", status_code=204)
async def delete_shadow_trade(
    trade_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific paper trade (must belong to the authenticated user)."""
    from sqlalchemy import select as sa_select

    from flowdesk_core.models.shadow_portfolio import ShadowTrade

    user_id = UUID(current_user["sub"])
    result = await db.execute(
        sa_select(ShadowTrade).where(ShadowTrade.id == trade_id, ShadowTrade.keycloak_id == user_id)
    )
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")
    await db.delete(trade)
    await db.commit()


@router.post("/portfolio/analyze")
async def analyze_shadow_portfolio(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    body: AILocaleBody = Body(default_factory=AILocaleBody),
):
    """Stream AI analysis of the user's shadow portfolio."""
    user_id = UUID(current_user["sub"])
    roles = _extract_roles(current_user)
    await _check_quota(db, user_id, roles)

    try:
        provider_name, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    ctx = await build_portfolio_context(db, user_id)
    if not ctx.get("has_data"):
        raise HTTPException(status_code=422, detail="No trades recorded. Add paper trades first.")

    prompt = render_portfolio_analysis_prompt(ctx, locale=body.locale)
    skill = get_skill("portfolio_doctor")  # scoped tools + heavy tier

    async def _stream_portfolio():
        try:
            async for chunk in run_skill(
                skill,
                db=db,
                user_id=str(user_id),
                user_text=prompt,
                symbols=[p["symbol"] for p in ctx.get("positions", [])],
                locale=body.locale,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            logger.error("Portfolio analysis stream error for user %s: %s", user_id, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': 'Portfolio analysis failed.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream_portfolio(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
