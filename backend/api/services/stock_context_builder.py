"""StockContextBuilder — assembles DB data into structured LLM-ready context.

Used by the AI insights endpoints (chart narration, morning brief, etc.)
to inject real FlowDesktop data into prompts rather than relying on the LLM's
training knowledge.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.models import HistoricalPrice, Quote, Stock
from flowdesk_core.models.enrichment import FundamentalDataRecord, MacroIndicatorRecord

logger = logging.getLogger(__name__)


def _lang_prefix(locale: str) -> str:
    """Return a hard language directive to prepend to prompts when locale is Chinese."""
    if locale.startswith("zh"):
        return (
            "【重要指示】请用简体中文回复本次分析。"
            "股票代码（如 AAPL、000858.SZ）、数字和百分比保持英文原样。\n\n"
        )
    return ""


def _h(locale: str) -> dict[str, str]:
    """Return locale-specific section header strings for prompt templates."""
    if locale.startswith("zh"):
        return {
            # analyze
            "price_snapshot": "价格快照",
            "technical": "技术面解读",
            "fundamentals": "基本面",
            "risk_flags": "风险提示",
            "bottom_line": "总结",
            # compare
            "overview": "概览",
            "price_action": "价格走势对比",
            "fund_compare": "基本面对比",
            "risk_profile": "风险特征",
            # macro
            "impact": "影响分析",
            "cross_market": "跨市场视角",
            # portfolio
            "portfolio_ovr": "组合概览",
            "perf_snapshot": "收益快照",
            "behavior": "行为模式",
            "watch": "关注要点",
        }
    return {
        "price_snapshot": "Price Snapshot",
        "technical": "Technical Reading",
        "fundamentals": "Fundamentals",
        "risk_flags": "Risk Flags",
        "bottom_line": "Bottom Line",
        "overview": "Overview",
        "price_action": "Price Action Comparison",
        "fund_compare": "Fundamental Comparison",
        "risk_profile": "Risk Profile",
        "impact": "Impact Analysis",
        "cross_market": "Cross-Market View",
        "portfolio_ovr": "Portfolio Overview",
        "perf_snapshot": "Performance Snapshot",
        "behavior": "Behavioral Patterns",
        "watch": "What to Watch",
    }


# Key FRED series we surface in the morning brief
_MACRO_SERIES = {
    "FEDFUNDS": "Fed Funds Rate",
    "CPIAUCSL": "US CPI (YoY)",
    "UNRATE": "US Unemployment Rate",
    "T10Y2Y": "10Y-2Y Yield Spread",
    "VIXCLS": "VIX (Volatility Index)",
    "DXY": "US Dollar Index",
}


def _fmt_price(v: Decimal | float | None, currency: str = "USD") -> str:
    if v is None:
        return "N/A"
    symbol = "$" if currency in ("USD", "HKD", "SGD", "TWD") else ""
    return f"{symbol}{float(v):,.2f}"


def _fmt_pct(v: Decimal | float | None) -> str:
    if v is None:
        return "N/A"
    sign = "+" if float(v) >= 0 else ""
    return f"{sign}{float(v):.2f}%"


def _fmt_cap(v: int | None) -> str:
    if v is None:
        return "N/A"
    if v >= 1_000_000_000_000:
        return f"${v / 1_000_000_000_000:.1f}T"
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    return f"${v:,}"


async def build_stock_context(db: AsyncSession, symbol: str) -> dict[str, Any] | None:
    """Return a structured dict with all available DB data for a symbol."""

    # 1. Stock metadata
    stock_result = await db.execute(select(Stock).where(Stock.symbol == symbol))
    stock = stock_result.scalar_one_or_none()
    if not stock:
        return None

    # 2. Latest quote
    quote_result = await db.execute(
        select(Quote).where(Quote.stock_id == stock.id).order_by(desc(Quote.timestamp)).limit(1)
    )
    quote = quote_result.scalar_one_or_none()

    # 3. Historical prices — last 90 days
    since = date.today() - timedelta(days=90)
    hist_result = await db.execute(
        select(HistoricalPrice)
        .where(
            HistoricalPrice.stock_id == stock.id,
            HistoricalPrice.date >= since,
        )
        .order_by(HistoricalPrice.date)
    )
    history = hist_result.scalars().all()

    # 4. 52-week high/low from historical
    year_ago = date.today() - timedelta(days=365)
    yw_result = await db.execute(
        select(
            func.max(HistoricalPrice.high).label("high_52w"),
            func.min(HistoricalPrice.low).label("low_52w"),
        ).where(
            HistoricalPrice.stock_id == stock.id,
            HistoricalPrice.date >= year_ago,
        )
    )
    yw = yw_result.one_or_none()

    # 5. Fundamentals (US stocks via SEC EDGAR — latest values per concept)
    fundamentals: dict[str, Any] = {}
    _KEY_CONCEPTS = [
        "us-gaap/Revenues",
        "us-gaap/NetIncomeLoss",
        "us-gaap/EarningsPerShareBasic",
        "us-gaap/Assets",
        "us-gaap/LongTermDebt",
        "us-gaap/CommonStockSharesOutstanding",
    ]
    for concept in _KEY_CONCEPTS:
        f_result = await db.execute(
            select(FundamentalDataRecord)
            .where(
                FundamentalDataRecord.symbol == symbol,
                FundamentalDataRecord.concept == concept,
            )
            .order_by(desc(FundamentalDataRecord.period_end))
            .limit(1)
        )
        rec = f_result.scalar_one_or_none()
        if rec:
            short = concept.split("/")[-1]
            fundamentals[short] = {
                "value": float(rec.value) if rec.value is not None else None,
                "unit": rec.unit,
                "period": rec.period_end.isoformat() if rec.period_end else None,
                "form": rec.form,
            }

    # Build price series summary (avoid dumping 90 rows into prompt)
    price_series: list[dict] = []
    for h in history[-30:]:  # last 30 trading days in context
        price_series.append(
            {
                "date": h.date.isoformat(),
                "close": float(h.close) if h.close else None,
                "volume": h.volume,
                "change_pct": (
                    float((h.close - h.open_price) / h.open_price * 100)
                    if h.close and h.open_price and h.open_price != 0
                    else None
                ),
            }
        )

    # Simple technicals computed from history
    closes = [float(h.close) for h in history if h.close]
    volumes = [h.volume for h in history if h.volume]

    ma20 = sum(closes[-20:]) / len(closes[-20:]) if len(closes) >= 20 else None
    ma50 = sum(closes[-50:]) / len(closes[-50:]) if len(closes) >= 50 else None
    avg_vol_20 = sum(volumes[-20:]) / len(volumes[-20:]) if len(volumes) >= 20 else None

    current_price = (
        float(quote.price) if quote and quote.price else (closes[-1] if closes else None)
    )
    prev_close = closes[-2] if len(closes) >= 2 else None
    daily_change_pct = (
        ((current_price - prev_close) / prev_close * 100) if current_price and prev_close else None
    )

    return {
        "symbol": symbol,
        "name": stock.name,
        "exchange": stock.exchange,
        "sector": stock.sector,
        "industry": stock.industry,
        "market_cap": stock.market_cap,
        "currency": stock.currency or "USD",
        "is_active": stock.is_active,
        "quote": {
            "price": current_price,
            "change_pct": float(quote.change_percent)
            if quote and quote.change_percent
            else daily_change_pct,
            "volume": quote.volume if quote else (volumes[-1] if volumes else None),
            "timestamp": quote.timestamp.isoformat() if quote and quote.timestamp else None,
        },
        "technicals": {
            "ma20": ma20,
            "ma50": ma50,
            "avg_volume_20d": avg_vol_20,
            "price_vs_ma20_pct": ((current_price - ma20) / ma20 * 100)
            if current_price and ma20
            else None,
            "high_52w": float(yw.high_52w) if yw and yw.high_52w else None,
            "low_52w": float(yw.low_52w) if yw and yw.low_52w else None,
            "pct_from_52w_high": (
                (current_price - float(yw.high_52w)) / float(yw.high_52w) * 100
                if current_price and yw and yw.high_52w
                else None
            ),
        },
        "price_series": price_series,
        "fundamentals": fundamentals,
    }


def render_stock_analysis_prompt(ctx: dict[str, Any], locale: str = "en") -> str:
    """Render a structured analysis prompt from stock context dict."""
    sym = ctx["symbol"]
    name = ctx["name"]
    exchange = ctx["exchange"] or ""
    sector = ctx["sector"] or "Unknown sector"
    currency = ctx["currency"]
    q = ctx["quote"]
    t = ctx["technicals"]
    f = ctx["fundamentals"]
    cap_str = _fmt_cap(ctx["market_cap"])

    price_str = _fmt_price(q["price"], currency)
    chg_str = _fmt_pct(q["change_pct"])

    def _fmt_series_row(p: dict) -> str:
        close = f"{p['close']:.2f}" if p["close"] is not None else "N/A"
        vol = f"{p['volume']:,}" if p["volume"] is not None else "N/A"
        chg = f", chg={p['change_pct']:+.1f}%" if p["change_pct"] is not None else ""
        return f"  {p['date']}: close={close}, vol={vol}{chg}"

    series_lines = "\n".join(_fmt_series_row(p) for p in ctx["price_series"][-15:])

    fund_lines: str
    if f:
        lines = []
        for k, v in f.items():
            val = v["value"]
            unit = v.get("unit", "")
            period = v.get("period", "")
            form = v.get("form", "")
            if val is not None:
                lines.append(f"  {k}: {val:,.0f} {unit} ({form}, {period})")
        fund_lines = (
            "\n".join(lines) if lines else "  Not available (non-US stock or not yet collected)"
        )
    else:
        fund_lines = "  Not available"

    ma20_str = f"{t['ma20']:.2f}" if t["ma20"] is not None else "N/A"
    ma50_str = f"{t['ma50']:.2f}" if t["ma50"] is not None else "N/A"
    vs_ma20_str = f"{t['price_vs_ma20_pct']:+.1f}%" if t["price_vs_ma20_pct"] is not None else "N/A"
    high52_str = f"{t['high_52w']:.2f}" if t["high_52w"] is not None else "N/A"
    low52_str = f"{t['low_52w']:.2f}" if t["low_52w"] is not None else "N/A"
    from52_str = f"{t['pct_from_52w_high']:+.1f}%" if t["pct_from_52w_high"] is not None else "N/A"
    vol_str = f"{q['volume']:,}" if q["volume"] is not None else "N/A"
    avg_vol_str = f"{int(t['avg_volume_20d']):,}" if t["avg_volume_20d"] is not None else "N/A"

    hdr = _h(locale)
    return (
        _lang_prefix(locale)
        + f"""You are FlowDesktop AI performing a structured stock analysis. Use ONLY the data provided below — do not invent figures or reference data not shown here.

=== STOCK DATA: {sym} ({name}) ===

Exchange: {exchange} | Sector: {sector} | Market Cap: {cap_str}

Current Price: {price_str} ({chg_str} today)
Volume today: {vol_str} | 20-day avg volume: {avg_vol_str}

Technicals:
  MA20: {ma20_str} | MA50: {ma50_str}
  Price vs MA20: {vs_ma20_str}
  52-week high: {high52_str} | 52-week low: {low52_str}
  % from 52w high: {from52_str}

Recent price history (last 15 trading days):
{series_lines}

Fundamentals (SEC EDGAR, US stocks only):
{fund_lines}

=== INSTRUCTIONS ===

Produce a structured analysis in this exact format:

**{hdr["price_snapshot"]}**
[1-2 sentences on current price, today's move, and position relative to 52w range]

**{hdr["technical"]}**
[2-3 sentences on trend (above/below MAs), momentum, volume pattern, and any notable price action in the series]

**{hdr["fundamentals"]}**
[1-2 sentences — only if fundamental data is available; otherwise state it is not available for this exchange]

**{hdr["risk_flags"]}**
[1-2 sentences on volatility, liquidity concerns, or any warning signs in the data]

**{hdr["bottom_line"]}**
[Exactly 2-3 sentences in plain language. Do not give a buy/sell recommendation. Summarize what the data shows and what a trader should watch.]

Keep the total response under 350 words. Be direct and data-grounded. Do not use phrases like "based on my analysis" or "it appears". State what the data shows.
"""
    )


async def build_morning_brief_context(
    db: AsyncSession,
    watchlist_symbols: list[str],
) -> dict[str, Any]:
    """Assemble context for a user's morning brief."""

    if not watchlist_symbols:
        return {"watchlist": [], "macro": [], "has_data": False}

    # Fetch stock metadata + latest quotes for watchlist
    stocks_result = await db.execute(select(Stock).where(Stock.symbol.in_(watchlist_symbols)))
    stocks_by_symbol = {s.symbol: s for s in stocks_result.scalars().all()}

    watchlist_data = []
    for sym in watchlist_symbols:
        stock = stocks_by_symbol.get(sym)
        if not stock:
            continue

        q_result = await db.execute(
            select(Quote).where(Quote.stock_id == stock.id).order_by(desc(Quote.timestamp)).limit(1)
        )
        quote = q_result.scalar_one_or_none()

        # Yesterday's close from historical
        hist_result = await db.execute(
            select(HistoricalPrice)
            .where(HistoricalPrice.stock_id == stock.id)
            .order_by(desc(HistoricalPrice.date))
            .limit(2)
        )
        hist = hist_result.scalars().all()
        prev_close = float(hist[1].close) if len(hist) >= 2 and hist[1].close else None

        current = float(quote.price) if quote and quote.price else None
        chg_pct = (
            float(quote.change_percent)
            if quote and quote.change_percent
            else (((current - prev_close) / prev_close * 100) if current and prev_close else None)
        )

        watchlist_data.append(
            {
                "symbol": sym,
                "name": stock.name,
                "exchange": stock.exchange,
                "sector": stock.sector,
                "price": current,
                "change_pct": chg_pct,
                "market_cap": stock.market_cap,
            }
        )

    # Fetch latest macro indicators
    macro_data = []
    for series_id, label in _MACRO_SERIES.items():
        m_result = await db.execute(
            select(MacroIndicatorRecord)
            .where(MacroIndicatorRecord.series_id == series_id)
            .order_by(desc(MacroIndicatorRecord.indicator_date))
            .limit(2)
        )
        records = m_result.scalars().all()
        if records:
            latest = records[0]
            prev = records[1] if len(records) > 1 else None
            change = None
            if latest.value is not None and prev and prev.value is not None:
                change = float(latest.value - prev.value)
            macro_data.append(
                {
                    "series": series_id,
                    "label": label,
                    "value": float(latest.value) if latest.value is not None else None,
                    "unit": latest.unit,
                    "date": latest.indicator_date.isoformat(),
                    "change": change,
                }
            )

    return {
        "watchlist": watchlist_data,
        "macro": macro_data,
        "has_data": bool(watchlist_data),
        "today": date.today().isoformat(),
    }


async def run_stock_screen(db: AsyncSession, filters: dict) -> list[dict]:
    """Execute a structured stock screen against stocks + quotes tables."""
    from sqlalchemy import and_, or_

    # Build stock filter query
    stmt = select(Stock).where(Stock.is_active == True)  # noqa: E712

    exchanges = filters.get("exchanges")
    if exchanges:
        stmt = stmt.where(Stock.exchange.in_(exchanges))

    sectors = filters.get("sectors")
    if sectors:
        stmt = stmt.where(or_(*[Stock.sector.ilike(f"%{s}%") for s in sectors]))

    market_cap_min = filters.get("market_cap_min")
    if market_cap_min is not None:
        stmt = stmt.where(Stock.market_cap >= market_cap_min)

    market_cap_max = filters.get("market_cap_max")
    if market_cap_max is not None:
        stmt = stmt.where(Stock.market_cap <= market_cap_max)

    # Fetch more stocks than limit to allow price/change filtering post-join
    pre_limit = min(int(filters.get("limit", 20)) * 5, 200)
    stmt = stmt.limit(pre_limit)

    stocks_result = await db.execute(stmt)
    stocks = stocks_result.scalars().all()

    if not stocks:
        return []

    # Fetch latest quote for each stock via a single IN query with subquery
    stock_ids = [s.id for s in stocks]
    latest_ts_sq = (
        select(Quote.stock_id, func.max(Quote.timestamp).label("max_ts"))
        .where(Quote.stock_id.in_(stock_ids))
        .group_by(Quote.stock_id)
        .subquery()
    )
    quotes_result = await db.execute(
        select(Quote).join(
            latest_ts_sq,
            and_(
                Quote.stock_id == latest_ts_sq.c.stock_id,
                Quote.timestamp == latest_ts_sq.c.max_ts,
            ),
        )
    )
    quotes_by_stock_id = {q.stock_id: q for q in quotes_result.scalars().all()}

    # Apply price and change filters, build output
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    change_min = filters.get("change_pct_min")
    change_max = filters.get("change_pct_max")
    limit = min(int(filters.get("limit", 20)), 50)

    out = []
    for stock in stocks:
        q = quotes_by_stock_id.get(stock.id)
        price = float(q.price) if q and q.price is not None else None
        change = float(q.change_percent) if q and q.change_percent is not None else None

        if price_min is not None and (price is None or price < price_min):
            continue
        if price_max is not None and (price is None or price > price_max):
            continue
        if change_min is not None and (change is None or change < change_min):
            continue
        if change_max is not None and (change is None or change > change_max):
            continue

        out.append(
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "exchange": stock.exchange,
                "sector": stock.sector,
                "price": price,
                "change_pct": change,
                "market_cap": stock.market_cap,
            }
        )
        if len(out) >= limit:
            break

    return out


async def build_comparison_context(db: AsyncSession, symbols: list[str]) -> dict:
    """Build context for comparing 2-3 stocks side by side."""
    stocks_ctx = []
    for sym in symbols:
        ctx = await build_stock_context(db, sym.upper())
        if ctx:
            stocks_ctx.append(ctx)
    return {"stocks": stocks_ctx}


def render_comparison_prompt(ctx: dict, locale: str = "en") -> str:
    """Render a head-to-head comparison prompt for 2-3 stocks."""
    stocks = ctx["stocks"]
    n = len(stocks)
    if n == 0:
        return "No stock data available for comparison."

    lines = [
        f"You are FlowDesktop AI comparing {n} stock{'s' if n > 1 else ''} side by side. "
        "Use ONLY the data provided below — do not invent figures.\n"
    ]

    for s in stocks:
        q = s["quote"]
        t = s["technicals"]
        cap_str = _fmt_cap(s["market_cap"])
        price_str = _fmt_price(q["price"], s["currency"])
        chg_str = _fmt_pct(q["change_pct"])
        ma20_str = f"{t['ma20']:.2f}" if t["ma20"] else "N/A"
        high52 = f"{t['high_52w']:.2f}" if t["high_52w"] else "N/A"
        low52 = f"{t['low_52w']:.2f}" if t["low_52w"] else "N/A"
        from52 = f"{t['pct_from_52w_high']:+.1f}%" if t["pct_from_52w_high"] is not None else "N/A"
        lines.append(
            f"--- {s['symbol']} ({s['name']}) ---\n"
            f"  Exchange: {s['exchange'] or 'N/A'} | Sector: {s['sector'] or 'N/A'} | Cap: {cap_str}\n"
            f"  Price: {price_str} ({chg_str}) | MA20: {ma20_str} | 52w: {low52}–{high52} ({from52} from high)\n"
        )
        if s["fundamentals"]:
            fund_items = []
            for k, v in list(s["fundamentals"].items())[:3]:
                if v["value"] is not None:
                    fund_items.append(f"{k}: {v['value']:,.0f} {v.get('unit', '')}")
            if fund_items:
                lines.append(f"  Fundamentals: {' | '.join(fund_items)}\n")

    hdr = _h(locale)
    lines.append(f"""
Produce a structured comparison:

**{hdr["overview"]}**
[1-2 sentences on what these stocks have in common and how they differ — sector, market, size]

**{hdr["price_action"]}**
[Bullet points: which is trending better, volume, 52w position]

**{hdr["fund_compare"]}**
[Revenue, earnings, etc. Only if SEC data exists; otherwise omit this section]

**{hdr["risk_profile"]}**
[Which carries more volatility/liquidity risk based on the data]

**{hdr["bottom_line"]}**
[2 sentences max. Do not recommend. State what the data shows about each.]

Keep it under 400 words. Be direct and data-grounded.
""")
    return _lang_prefix(locale) + "\n".join(lines)


async def build_macro_impact_context(
    db: AsyncSession, macro_event: str, watchlist_symbols: list[str]
) -> dict:
    """Build context for macro impact analysis."""
    # Reuse morning brief context builder for watchlist + macro data
    ctx = await build_morning_brief_context(db, watchlist_symbols)
    return {**ctx, "macro_event": macro_event}


def render_macro_impact_prompt(ctx: dict, macro_event: str, locale: str = "en") -> str:
    """Render macro impact analysis prompt."""
    watchlist = ctx.get("watchlist", [])
    macro = ctx.get("macro", [])

    def _fmt_wl(w: dict) -> str:
        cap_str = _fmt_cap(w.get("market_cap"))
        return f"  {w['symbol']} ({w['name']}, {w.get('exchange', '?')}, {w.get('sector', '?')}, cap={cap_str})"

    watchlist_lines = "\n".join(_fmt_wl(w) for w in watchlist) or "  No watchlist data."
    macro_lines = (
        "\n".join(
            f"  {m['label']}: {m['value']} {m.get('unit', '') or ''} as of {m['date']}"
            for m in macro
        )
        or "  No macro data available."
    )

    hdr = _h(locale)
    return (
        _lang_prefix(locale)
        + f"""You are FlowDesktop AI analyzing the potential impact of a macro event on a user's watchlist.
Macro event: {macro_event}

=== WATCHLIST ===
{watchlist_lines}

=== CURRENT MACRO INDICATORS (FRED) ===
{macro_lines}

=== INSTRUCTIONS ===

For each stock in the watchlist, assess the likely impact direction of this macro event:

**{hdr["impact"]} — {macro_event}**

For each stock:
- **{{SYMBOL}}** ({{name}}, {{sector}}, {{exchange}}): [impact assessment — positive/negative/neutral, 1-2 sentences of reasoning based on sector/exchange exposure. Cite macro data where relevant.]

**{hdr["cross_market"]}**
[1-2 sentences on how this event ripples across the different exchanges in the watchlist]

Keep it under 400 words. No buy/sell recommendations. State what the data suggests.
"""
    )


def render_committee_prompt(stock_ctx: dict, role: str, locale: str = "en") -> str:
    """Render a committee debate prompt for one role: 'bull', 'bear', or 'risk'."""
    sym = stock_ctx["symbol"]
    name = stock_ctx["name"]
    q = stock_ctx["quote"]
    t = stock_ctx["technicals"]
    cap_str = _fmt_cap(stock_ctx["market_cap"])
    price_str = _fmt_price(q["price"], stock_ctx["currency"])
    chg_str = _fmt_pct(q["change_pct"])
    ma20_str = f"{t['ma20']:.2f}" if t["ma20"] else "N/A"
    high52 = f"{t['high_52w']:.2f}" if t["high_52w"] else "N/A"
    low52 = f"{t['low_52w']:.2f}" if t["low_52w"] else "N/A"
    from52 = f"{t['pct_from_52w_high']:+.1f}%" if t["pct_from_52w_high"] is not None else "N/A"
    fund_lines = ""
    if stock_ctx["fundamentals"]:
        items = []
        for k, v in stock_ctx["fundamentals"].items():
            if v["value"] is not None:
                items.append(f"{k}: {v['value']:,.0f} {v.get('unit', '')}")
        fund_lines = " | ".join(items[:4]) if items else ""

    data_block = (
        f"{sym} ({name}) | {stock_ctx.get('exchange', '?')} | {stock_ctx.get('sector', '?')} | Cap: {cap_str}\n"
        f"Price: {price_str} ({chg_str}) | MA20: {ma20_str} | 52w range: {low52}–{high52} ({from52} from high)\n"
        + (f"Fundamentals: {fund_lines}\n" if fund_lines else "")
    )

    role_instructions = {
        "bull": (
            "You are the Bull Agent. Make the strongest case FOR holding this stock based ONLY on the data provided. "
            "Focus on positives in price action, fundamentals, sector trends visible in the numbers."
        ),
        "bear": (
            "You are the Bear Agent. Make the strongest case AGAINST this stock based ONLY on the data provided. "
            "Focus on weaknesses, risks, warning signs visible in the numbers."
        ),
        "risk": (
            "You are the Risk Agent. Quantify the downside scenarios based ONLY on the data provided. "
            "State the key risk factors, potential drawdown scenarios based on the 52w range, and liquidity concerns."
        ),
    }
    instruction = role_instructions.get(role, role_instructions["bull"])

    return (
        _lang_prefix(locale)
        + f"""{instruction}

=== STOCK DATA ===
{data_block}

Write 100-150 words maximum. Be concise and data-grounded. No buy/sell recommendations.
"""
    )


async def run_strategy_backtest(db: AsyncSession, symbol: str, rules: dict) -> dict:
    """Run a simple rule-based backtest against historical_prices.

    rules: {
        "entry_condition": "rsi_below" | "consecutive_down_days" | "price_below_ma",
        "entry_threshold": float,
        "exit_days": int,
    }
    """

    # Fetch historical prices (up to 2 years)
    two_years_ago = date.today() - timedelta(days=730)
    stock_result = await db.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    stock = stock_result.scalar_one_or_none()
    if not stock:
        return {"error": f"Symbol {symbol} not found", "num_trades": 0}

    hist_result = await db.execute(
        select(HistoricalPrice)
        .where(
            HistoricalPrice.stock_id == stock.id,
            HistoricalPrice.date >= two_years_ago,
        )
        .order_by(HistoricalPrice.date)
    )
    history = hist_result.scalars().all()
    closes = [float(h.close) for h in history if h.close]

    if len(closes) < 30:
        return {
            "error": "Insufficient historical data",
            "num_trades": 0,
            "closes_count": len(closes),
        }

    # Compute MA20
    ma20_series = [None] * len(closes)
    for i in range(19, len(closes)):
        ma20_series[i] = sum(closes[i - 19 : i + 1]) / 20

    # Compute simple RSI-14 using exponential smoothing
    rsi_series = [None] * len(closes)
    if len(closes) >= 15:
        gains = []
        losses = []
        for i in range(1, 15):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        for i in range(14, len(closes)):
            diff = closes[i] - closes[i - 1]
            g = max(diff, 0)
            lo = max(-diff, 0)
            avg_gain = (avg_gain * 13 + g) / 14
            avg_loss = (avg_loss * 13 + lo) / 14
            if avg_loss == 0:
                rsi_series[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_series[i] = 100 - (100 / (1 + rs))

    # Simulate trades
    entry_condition = rules.get("entry_condition", "rsi_below")
    threshold = float(rules.get("entry_threshold", 30))
    exit_days = int(rules.get("exit_days", 10))

    trades = []
    in_trade = False
    entry_idx = 0
    entry_price = 0.0

    for i in range(20, len(closes)):
        if not in_trade:
            signal = False
            if entry_condition == "rsi_below" and rsi_series[i] is not None:
                signal = rsi_series[i] < threshold
            elif entry_condition == "consecutive_down_days":
                days = int(threshold)
                if i >= days:
                    signal = all(closes[j] < closes[j - 1] for j in range(i - days + 1, i + 1))
            elif entry_condition == "price_below_ma" and ma20_series[i] is not None:
                pct = threshold / 100.0
                signal = closes[i] < ma20_series[i] * (1 - pct)

            if signal:
                in_trade = True
                entry_idx = i
                entry_price = closes[i]
        else:
            if i - entry_idx >= exit_days:
                exit_price = closes[i]
                ret = (exit_price - entry_price) / entry_price * 100
                trades.append(
                    {
                        "entry": entry_price,
                        "exit": exit_price,
                        "return_pct": ret,
                        "hold_days": i - entry_idx,
                    }
                )
                in_trade = False

    if not trades:
        return {
            "symbol": symbol,
            "entry_condition": entry_condition,
            "threshold": threshold,
            "exit_days": exit_days,
            "num_trades": 0,
            "win_rate": None,
            "avg_return_pct": None,
            "max_drawdown_pct": None,
            "avg_hold_days": exit_days,
            "data_points": len(closes),
        }

    wins = sum(1 for t in trades if t["return_pct"] > 0)
    returns = [t["return_pct"] for t in trades]
    avg_return = sum(returns) / len(returns)
    max_dd = min(returns)
    avg_hold = sum(t["hold_days"] for t in trades) / len(trades)

    return {
        "symbol": symbol,
        "entry_condition": entry_condition,
        "threshold": threshold,
        "exit_days": exit_days,
        "num_trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1),
        "avg_return_pct": round(avg_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "avg_hold_days": round(avg_hold, 1),
        "data_points": len(closes),
    }


async def build_portfolio_context(db: AsyncSession, user_id) -> dict:
    """Build shadow portfolio analysis context."""

    from flowdesk_core.models.shadow_portfolio import ShadowTrade

    # Fetch all trades
    trades_result = await db.execute(
        select(ShadowTrade)
        .where(ShadowTrade.keycloak_id == user_id)
        .order_by(ShadowTrade.trade_date)
    )
    trades = trades_result.scalars().all()
    if not trades:
        return {"trades": [], "positions": [], "summary": {}, "has_data": False}

    # Group by symbol to compute positions
    from collections import defaultdict

    symbol_trades: dict = defaultdict(list)
    for t in trades:
        symbol_trades[t.symbol].append(t)

    all_symbols = list(symbol_trades.keys())

    # Fetch current quotes
    stocks_result = await db.execute(select(Stock).where(Stock.symbol.in_(all_symbols)))
    stocks_by_symbol = {s.symbol: s for s in stocks_result.scalars().all()}

    current_prices: dict = {}
    for sym, stock in stocks_by_symbol.items():
        q_result = await db.execute(
            select(Quote).where(Quote.stock_id == stock.id).order_by(desc(Quote.timestamp)).limit(1)
        )
        q = q_result.scalar_one_or_none()
        if q and q.price:
            current_prices[sym] = float(q.price)

    positions = []
    for sym, sym_trades in symbol_trades.items():
        shares_held = 0.0
        cost_basis = 0.0
        buy_trades = [t for t in sym_trades if t.action.lower() == "buy"]
        sell_trades = [t for t in sym_trades if t.action.lower() == "sell"]

        for t in buy_trades:
            shares_held += float(t.shares)
            cost_basis += float(t.shares) * float(t.price)
        for t in sell_trades:
            shares_held -= float(t.shares)

        if shares_held <= 0:
            continue

        avg_cost = cost_basis / sum(float(t.shares) for t in buy_trades) if buy_trades else 0
        current_price = current_prices.get(sym)
        unrealized_pnl_pct = (
            ((current_price - avg_cost) / avg_cost * 100) if current_price and avg_cost else None
        )

        positions.append(
            {
                "symbol": sym,
                "shares": round(shares_held, 4),
                "avg_cost": round(avg_cost, 4),
                "current_price": current_price,
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2)
                if unrealized_pnl_pct is not None
                else None,
            }
        )

    winning = sum(1 for p in positions if p["unrealized_pnl_pct"] and p["unrealized_pnl_pct"] > 0)
    losing = sum(1 for p in positions if p["unrealized_pnl_pct"] and p["unrealized_pnl_pct"] < 0)

    # Compute sector breakdown
    sector_counts: dict = defaultdict(int)
    for sym in all_symbols:
        stock = stocks_by_symbol.get(sym)
        if stock and stock.sector:
            sector_counts[stock.sector] += 1

    return {
        "trades": [
            {
                "symbol": t.symbol,
                "action": t.action,
                "shares": float(t.shares),
                "price": float(t.price),
                "trade_date": t.trade_date.isoformat(),
                "note": t.note,
            }
            for t in trades
        ],
        "positions": positions,
        "summary": {
            "total_trades": len(trades),
            "total_positions": len(positions),
            "winning_positions": winning,
            "losing_positions": losing,
            "top_sectors": dict(sorted(sector_counts.items(), key=lambda x: -x[1])[:5]),
        },
        "has_data": True,
    }


def render_portfolio_analysis_prompt(ctx: dict, locale: str = "en") -> str:
    """Render shadow portfolio analysis prompt."""
    summary = ctx.get("summary", {})
    positions = ctx.get("positions", [])

    pos_lines = []
    for p in positions:
        pnl_str = (
            f"{p['unrealized_pnl_pct']:+.1f}%" if p["unrealized_pnl_pct"] is not None else "N/A"
        )
        pos_lines.append(
            f"  {p['symbol']}: {p['shares']} shares @ avg cost {p['avg_cost']:.2f}, "
            f"current: {p['current_price'] or 'N/A'}, unrealized P&L: {pnl_str}"
        )
    positions_block = "\n".join(pos_lines) or "  No open positions."

    hdr = _h(locale)
    return (
        _lang_prefix(locale)
        + f"""You are FlowDesktop AI analyzing a user's shadow (paper trading) portfolio.

=== PORTFOLIO SUMMARY ===
Total trades recorded: {summary.get("total_trades", 0)}
Open positions: {summary.get("total_positions", 0)}
Winning positions: {summary.get("winning_positions", 0)}
Losing positions: {summary.get("losing_positions", 0)}
Sectors: {", ".join(summary.get("top_sectors", {}).keys()) or "N/A"}

=== OPEN POSITIONS ===
{positions_block}

=== INSTRUCTIONS ===

Analyze this paper trading portfolio and provide:

**{hdr["portfolio_ovr"]}**
[1-2 sentences on the overall composition — sector concentration, market exposure, diversity]

**{hdr["perf_snapshot"]}**
[Which positions are working, which are struggling. Only reference the P&L data provided.]

**{hdr["behavior"]}**
[Identify any patterns: sector concentration, position sizing, entry timing signals visible in the data]

**{hdr["watch"]}**
[1-2 actionable observations based purely on the numbers — not buy/sell recommendations]

Keep it under 300 words. Be direct. No financial advice.
"""
    )


def render_morning_brief_prompt(ctx: dict[str, Any]) -> str:
    """Render the morning brief prompt from assembled context."""
    today = ctx["today"]
    watchlist = ctx["watchlist"]
    macro = ctx["macro"]

    movers = [w for w in watchlist if w["change_pct"] is not None and abs(w["change_pct"]) >= 1.5]
    movers.sort(key=lambda x: abs(x["change_pct"] or 0), reverse=True)

    def _fmt_watchlist_row(w: dict) -> str:
        if w["change_pct"] is None:
            return f"  {w['symbol']} ({w['name']}): no quote data yet"
        price_str = "N/A" if w["price"] is None else f"{w['price']:.2f}"
        sign = "+" if (w["change_pct"] or 0) >= 0 else ""
        return (
            f"  {w['symbol']} ({w['name']}, {w['exchange']}): "
            f"{price_str} ({sign}{w['change_pct']:.1f}% today)"
        )

    watchlist_lines = "\n".join(_fmt_watchlist_row(w) for w in watchlist)

    macro_lines = (
        "\n".join(
            f"  {m['label']}: {m['value']} {m['unit'] or ''} as of {m['date']}"
            + (f" (Δ {m['change']:+.3f} vs prior)" if m["change"] is not None else "")
            for m in macro
        )
        or "  No macro data available yet."
    )

    return f"""You are FlowDesktop AI generating a concise morning market brief for today ({today}).
Use ONLY the data provided. Do not reference events, news, or figures not shown here.

=== USER'S WATCHLIST ===
{watchlist_lines if watchlist_lines else "  No stocks in watchlist."}

=== MACRO INDICATORS (FRED) ===
{macro_lines}

=== INSTRUCTIONS ===

Write a morning brief in this exact format:

**Market Mood**
[1 sentence — broad characterization based only on the macro data above. If macro data is sparse, say so honestly.]

**Watchlist Highlights**
[Mention the top 2–3 movers from the watchlist with their change. If nothing moved >1.5%, note that the watchlist is quiet today.]

**Macro Watch**
[1–2 sentences on any notable macro reading — elevated VIX, yield spread inversion, rate changes. Skip if no meaningful signal.]

**One Thing to Watch**
[1 sentence — the single most actionable observation from this data for a stock trader today.]

Keep the total under 200 words. Be direct and specific. Do not invent data.
"""
