"""Simulator money math — pure compute_fill + rounding (no DB)."""

from decimal import Decimal

from api.services.simulation import _round_cash, _round_price, compute_fill


def test_buy_no_friction():
    f = compute_fill("buy", Decimal(10), Decimal("100"), 0, 0)
    assert f["exec_price"] == Decimal("100.000000")
    assert f["gross"] == Decimal("1000.0000")
    assert f["fee"] == Decimal("0.0000")
    assert f["cash_delta"] == Decimal("-1000.0000")


def test_sell_no_friction():
    f = compute_fill("sell", Decimal(10), Decimal("100"), 0, 0)
    assert f["cash_delta"] == Decimal("1000.0000")


def test_commission_charged_both_sides():
    b = compute_fill("buy", Decimal(10), Decimal("100"), 10, 0)  # 10bps of 1000 = 1.0
    assert b["fee"] == Decimal("1.0000")
    assert b["cash_delta"] == Decimal("-1001.0000")
    s = compute_fill("sell", Decimal(10), Decimal("100"), 10, 0)
    assert s["fee"] == Decimal("1.0000")
    assert s["cash_delta"] == Decimal("999.0000")


def test_slippage_buy_raises_sell_lowers():
    b = compute_fill("buy", Decimal(1), Decimal("100"), 0, 100)  # 100bps = 1% → 101
    assert b["exec_price"] == Decimal("101.000000")
    s = compute_fill("sell", Decimal(1), Decimal("100"), 0, 100)  # → 99
    assert s["exec_price"] == Decimal("99.000000")


def test_fractional_price_rounding():
    f = compute_fill("buy", Decimal(3), Decimal("33.333333"), 0, 0)
    # 3 * 33.333333 = 99.999999 → rounded cash 4dp
    assert f["gross"] == Decimal("100.0000")


def test_rounding_helpers():
    assert _round_cash(Decimal("1.23456")) == Decimal("1.2346")
    assert _round_price(Decimal("1.2345678")) == Decimal("1.234568")
