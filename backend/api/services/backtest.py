"""Lightweight backtest engine for the Strategy Architect agent.

Pure functions over a close-price series — no DB, no network — so they're easy
to unit-test. Two simple, well-defined strategies (SMA crossover, RSI mean
reversion) vs a buy & hold baseline. Long/flat only, all-in/all-out, no costs;
positions decided on day i apply to the return from i→i+1 (next-bar execution,
so there's no look-ahead bias).
"""

from __future__ import annotations

import math
import statistics


def _sma(vals: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(vals)
    if n <= 0:
        return out
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= n:
            s -= vals[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def _rsi(vals: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(vals)
    if period <= 0 or len(vals) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = vals[i] - vals[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag = gains / period
    al = losses / period
    out[period] = 100 - 100 / (1 + (ag / al if al else 1e9))
    for i in range(period + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        ag = (ag * (period - 1) + max(d, 0.0)) / period
        al = (al * (period - 1) + max(-d, 0.0)) / period
        rs = ag / al if al else 1e9
        out[i] = 100 - 100 / (1 + rs)
    return out


def _signals_sma(closes: list[float], fast: int, slow: int) -> list[int]:
    f = _sma(closes, fast)
    s = _sma(closes, slow)
    pos = [0] * len(closes)
    for i in range(len(closes)):
        if f[i] is None or s[i] is None:
            pos[i] = pos[i - 1] if i > 0 else 0
        else:
            pos[i] = 1 if f[i] > s[i] else 0
    return pos


def _signals_rsi(closes: list[float], period: int, oversold: float, overbought: float) -> list[int]:
    r = _rsi(closes, period)
    pos = [0] * len(closes)
    cur = 0
    for i in range(len(closes)):
        if r[i] is not None:
            if r[i] < oversold:
                cur = 1
            elif r[i] > overbought:
                cur = 0
        pos[i] = cur
    return pos


def run_backtest(dates: list[str], closes: list[float], strategy: str, params: dict) -> dict:
    """Backtest `strategy` over a close series; return metrics + equity curves."""
    n = len(closes)
    if n < 30:
        return {"error": "Not enough history to backtest (need ≥30 days)."}

    if strategy == "sma_crossover":
        fast = int(params.get("fast") or 20)
        slow = int(params.get("slow") or 50)
        if fast >= slow:
            fast, slow = 20, 50
        pos = _signals_sma(closes, fast, slow)
        label = f"SMA {fast}/{slow} crossover"
    elif strategy == "rsi":
        period = int(params.get("period") or 14)
        oversold = float(params.get("oversold") or 30)
        overbought = float(params.get("overbought") or 70)
        pos = _signals_rsi(closes, period, oversold, overbought)
        label = f"RSI({period}) {oversold:g}/{overbought:g}"
    else:
        return {"error": f"Unknown strategy '{strategy}'. Use 'sma_crossover' or 'rsi'."}

    daily: list[float] = []
    equity = 1.0
    eq_curve = [1.0]
    bh = 1.0
    bh_curve = [1.0]
    total_trades = wins = 0
    entry: float | None = None

    for i in range(1, n):
        r = (closes[i] / closes[i - 1] - 1) if closes[i - 1] else 0.0
        held = pos[i - 1]  # yesterday's signal → today's holding (next-bar exec)
        eq_ret = r if held else 0.0
        equity *= 1 + eq_ret
        bh *= 1 + r
        eq_curve.append(equity)
        bh_curve.append(bh)
        daily.append(eq_ret)
        if held and entry is None:
            entry = closes[i - 1]
        elif (not held) and entry is not None:
            total_trades += 1
            wins += 1 if closes[i - 1] > entry else 0
            entry = None
    if entry is not None:
        total_trades += 1
        wins += 1 if closes[-1] > entry else 0

    peak = eq_curve[0]
    mdd = 0.0
    for v in eq_curve:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)

    if len(daily) > 1 and statistics.pstdev(daily) > 0:
        sharpe = (statistics.mean(daily) / statistics.pstdev(daily)) * math.sqrt(252)
    else:
        sharpe = 0.0

    return {
        "strategy_label": label,
        "days": n,
        "total_return_pct": round((equity - 1) * 100, 2),
        "buy_hold_return_pct": round((bh - 1) * 100, 2),
        "max_drawdown_pct": round(mdd * 100, 2),
        "sharpe": round(sharpe, 2),
        "trades": total_trades,
        "win_rate_pct": round((wins / total_trades) * 100, 1) if total_trades else 0.0,
        "_curves": {"dates": dates, "strategy": eq_curve, "buy_hold": bh_curve},
    }
