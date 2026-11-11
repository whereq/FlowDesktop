"""Simulator matcher — pure limit-cross + day-order expiry helpers (no DB)."""

from datetime import datetime
from decimal import Decimal

from api.services.simulation import _end_of_utc_day, limit_crosses


def test_buy_limit_crosses_at_or_below():
    assert limit_crosses("buy", Decimal("49"), Decimal("50")) is True  # below → fill
    assert limit_crosses("buy", Decimal("50"), Decimal("50")) is True  # at → fill
    assert limit_crosses("buy", Decimal("51"), Decimal("50")) is False  # above → wait


def test_sell_limit_crosses_at_or_above():
    assert limit_crosses("sell", Decimal("51"), Decimal("50")) is True  # above → fill
    assert limit_crosses("sell", Decimal("50"), Decimal("50")) is True  # at → fill
    assert limit_crosses("sell", Decimal("49"), Decimal("50")) is False  # below → wait


def test_limit_crosses_accepts_non_decimal():
    assert limit_crosses("buy", 49, 50) is True
    assert limit_crosses("sell", "51", "50") is True


def test_end_of_utc_day():
    d = _end_of_utc_day(datetime(2026, 7, 1, 14, 30, 0))
    assert d == datetime(2026, 7, 1, 23, 59, 59)
