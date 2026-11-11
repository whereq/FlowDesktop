"""Simulator order validation — pure validate_order (no DB)."""

from decimal import Decimal

from api.services.simulation import validate_order

BASE = {
    "account_active": True,
    "account_currency": "USD",
    "stock_active": True,
    "stock_currency": "USD",
    "side": "buy",
    "order_type": "market",
    "quantity": Decimal(10),
    "limit_price": None,
    "ref_price": Decimal("100"),
    "held_qty": Decimal(0),
    "cash_balance": Decimal("100000"),
    "lot": 1,
    "commission_bps": 0.0,
}


def _v(**over):
    return validate_order(**{**BASE, **over})


def test_valid_market_buy():
    assert _v() is None


def test_currency_isolation_rejected():
    assert "not tradable" in _v(stock_currency="CNY")


def test_inactive_stock_rejected():
    assert "delisted" in _v(stock_active=False)


def test_inactive_account_rejected():
    assert "inactive" in _v(account_active=False)


def test_nonpositive_quantity_rejected():
    assert "positive" in _v(quantity=Decimal(0))


def test_lot_multiple_enforced():
    assert "multiple of 100" in _v(lot=100, quantity=Decimal(150))


def test_lot_multiple_ok():
    assert _v(lot=100, quantity=Decimal(200)) is None


def test_limit_requires_price():
    assert "limit price" in _v(order_type="limit", limit_price=None)


def test_insufficient_buying_power_rejected():
    assert "buying power" in _v(
        quantity=Decimal(2000), ref_price=Decimal("100"), cash_balance=Decimal("1000")
    )


def test_sell_more_than_held_rejected():
    assert "shorting" in _v(side="sell", quantity=Decimal(10), held_qty=Decimal(5))


def test_sell_within_holdings_ok():
    assert _v(side="sell", quantity=Decimal(5), held_qty=Decimal(10)) is None


def test_limit_buy_uses_limit_price_for_affordability():
    # 100 @ $50 = $5000 ≤ $6000 cash
    assert (
        _v(
            order_type="limit",
            limit_price=Decimal("50"),
            quantity=Decimal(100),
            cash_balance=Decimal("6000"),
        )
        is None
    )


def test_commission_pushes_buy_over_cash():
    # 100 @ $100 = $10,000; with 100bps commission ($100) est = $10,100 > $10,050
    assert "buying power" in _v(
        quantity=Decimal(100),
        ref_price=Decimal("100"),
        cash_balance=Decimal("10050"),
        commission_bps=100.0,
    )


def test_market_buy_no_price_rejected():
    assert "no recent price" in _v(ref_price=None)
