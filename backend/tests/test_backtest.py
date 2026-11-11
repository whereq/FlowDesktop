"""Backtest engine — pure-function metrics over a price series."""

from api.services.backtest import _rsi, _sma, run_backtest


def _dates(n):
    return [f"2026-01-{i + 1:02d}" for i in range(n)]


def test_sma_helper_basic():
    assert _sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]


def test_rsi_all_gains_is_high():
    vals = [float(i) for i in range(1, 40)]  # strictly rising
    r = _rsi(vals, 14)
    assert r[-1] is not None and r[-1] > 90  # pure uptrend → RSI near 100


def test_too_little_history_errors():
    out = run_backtest(_dates(10), [1.0] * 10, "sma_crossover", {})
    assert "error" in out


def test_unknown_strategy_errors():
    n = 60
    out = run_backtest(_dates(n), [float(i + 1) for i in range(n)], "nope", {})
    assert "error" in out


def test_uptrend_sma_crossover_profits():
    n = 120
    closes = [100 * (1.01**i) for i in range(n)]  # ~1%/day uptrend
    out = run_backtest(_dates(n), closes, "sma_crossover", {"fast": 10, "slow": 30})
    assert "error" not in out
    assert out["strategy_label"].startswith("SMA 10/30")
    assert out["total_return_pct"] > 0
    assert out["buy_hold_return_pct"] > 0
    assert out["days"] == n
    # curves are returned and aligned with the date series
    assert len(out["_curves"]["strategy"]) == n
    assert len(out["_curves"]["buy_hold"]) == n
    assert isinstance(out["sharpe"], float)


def test_metrics_shape():
    n = 80
    closes = [100 + (i % 7) - 3 for i in range(n)]  # choppy
    out = run_backtest(_dates(n), [float(c) for c in closes], "rsi", {"period": 14})
    assert {"total_return_pct", "max_drawdown_pct", "sharpe", "trades", "win_rate_pct"} <= set(out)
    assert out["max_drawdown_pct"] <= 0
