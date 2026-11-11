"""Simulator NOVA tools (P4) — pure propose + handler-level get_sim_portfolio.

The propose path is fully testable without a DB: ToolRegistry._propose returns a
plain dict containing a structured `_proposal` that the gateway forwards to the
frontend as an `action_proposal` SSE event. Crucially, _propose must NEVER write
to the DB — the frontend's existing /me/sim/* endpoint is the single writer.

For get_sim_portfolio we patch the sim_service and the DB execute() so the
owner-scoping branch is verifiable without standing up Postgres.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.tool_registry import ToolRegistry

# ---------------------------------------------------------------------------
# propose_sim_order  (pure: no DB; just validates args + builds the proposal)
# ---------------------------------------------------------------------------


def _reg() -> ToolRegistry:
    return ToolRegistry()


def test_propose_sim_order_market_buy_returns_well_formed_proposal():
    reg = _reg()
    out = reg._propose(
        "sim_order",
        {
            "account_id": 42,
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "market",
            "quantity": 20,
        },
        user_id="00000000-0000-0000-0000-000000000001",
    )
    assert "error" not in out
    assert out["status"] == "awaiting_user_confirmation"
    p = out["_proposal"]
    assert p["action"] == "sim_order"
    assert p["label"] == "Buy 20 AAPL (sim)"
    assert p["args"] == {
        "account_id": 42,
        "symbol": "AAPL",
        "side": "buy",
        "order_type": "market",
        "quantity": 20.0,
    }
    # Market orders drop any limit_price the model may have hallucinated.
    assert "limit_price" not in p["args"]


def test_propose_sim_order_limit_sell_includes_limit_price():
    reg = _reg()
    out = reg._propose(
        "sim_order",
        {
            "account_id": 7,
            "symbol": "NVDA",
            "side": "sell",
            "order_type": "limit",
            "quantity": 5,
            "limit_price": 905.50,
        },
        user_id="u-1",
    )
    assert "error" not in out
    p = out["_proposal"]
    assert p["label"] == "Sell 5 NVDA @ 905.5 (sim)"
    assert p["args"]["limit_price"] == 905.5
    assert p["args"]["order_type"] == "limit"


def test_propose_sim_order_uppercases_symbol_and_normalises_side():
    reg = _reg()
    out = reg._propose(
        "sim_order",
        {
            "account_id": 1,
            "symbol": "  aapl ",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 1,
        },
        user_id="u",
    )
    p = out["_proposal"]
    assert p["args"]["symbol"] == "AAPL"
    assert p["args"]["side"] == "buy"
    assert p["args"]["order_type"] == "market"


@pytest.mark.parametrize(
    "bad_args,err_substr",
    [
        (
            {
                "account_id": "x",
                "symbol": "AAPL",
                "side": "buy",
                "order_type": "market",
                "quantity": 1,
            },
            "account_id",
        ),
        ({"account_id": 1, "side": "buy", "order_type": "market", "quantity": 1}, "symbol"),
        (
            {
                "account_id": 1,
                "symbol": "AAPL",
                "side": "hold",
                "order_type": "market",
                "quantity": 1,
            },
            "side",
        ),
        (
            {"account_id": 1, "symbol": "AAPL", "side": "buy", "order_type": "stop", "quantity": 1},
            "order_type",
        ),
        (
            {
                "account_id": 1,
                "symbol": "AAPL",
                "side": "buy",
                "order_type": "market",
                "quantity": 0,
            },
            "quantity",
        ),
        (
            {
                "account_id": 1,
                "symbol": "AAPL",
                "side": "buy",
                "order_type": "market",
                "quantity": -5,
            },
            "quantity",
        ),
        (
            {
                "account_id": 1,
                "symbol": "AAPL",
                "side": "buy",
                "order_type": "limit",
                "quantity": 1,
            },
            "limit_price",
        ),
        (
            {
                "account_id": 1,
                "symbol": "AAPL",
                "side": "buy",
                "order_type": "limit",
                "quantity": 1,
                "limit_price": -1,
            },
            "limit_price",
        ),
    ],
)
def test_propose_sim_order_rejects_bad_args(bad_args, err_substr):
    reg = _reg()
    out = reg._propose("sim_order", bad_args, user_id="u-1")
    assert "error" in out
    assert err_substr in out["error"].lower()


def test_propose_sim_order_requires_authenticated_user():
    reg = _reg()
    out = reg._propose(
        "sim_order",
        {
            "account_id": 1,
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "market",
            "quantity": 1,
        },
        user_id=None,
    )
    assert "error" in out
    assert "authenticated" in out["error"].lower()


def test_propose_sim_order_never_writes(monkeypatch):
    """Belt-and-braces: no path inside _propose should ever touch a session."""
    reg = _reg()
    sentinel = MagicMock()
    monkeypatch.setattr("api.services.tool_registry.AsyncSessionLocal", sentinel, raising=False)
    out = reg._propose(
        "sim_order",
        {
            "account_id": 1,
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "market",
            "quantity": 1,
        },
        user_id="u-1",
    )
    assert "_proposal" in out
    # The registry must not have called any session, transaction, or execute.
    assert sentinel.call_count == 0
    # And there is no hidden side-effect key in the payload.
    for k in ("status", "_proposal", "summary"):
        assert k in out


# ---------------------------------------------------------------------------
# get_sim_portfolio  (owner-scoping; patched DB)
# ---------------------------------------------------------------------------


def _account(
    id_: int,
    name: str,
    currency: str = "USD",
    initial: str = "100000",
    cash: str = "100000",
    is_active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        name=name,
        currency=currency,
        initial_balance=initial,
        cash_balance=cash,
        is_active=is_active,
        keycloak_id="00000000-0000-0000-0000-000000000099",
    )


def test_get_sim_portfolio_no_user_returns_error():
    reg = _reg()
    db = MagicMock()
    out = asyncio.run(reg._get_sim_portfolio(db, user_id=None, account_id=None))
    assert out == {"error": "User not authenticated"}


def test_get_sim_portfolio_specific_account_owner_match_returns_value():
    """Owner-scoping happy path: account belongs to caller → full valuation."""
    from decimal import Decimal

    reg = _reg()
    db = MagicMock()
    acct = _account(7, "USD main", cash=Decimal("100000"), initial=Decimal("100000"))
    with patch("api.services.tool_registry.sim_service") as svc:
        svc.get_account = AsyncMock(return_value=acct)
        svc.value_account = AsyncMock(
            return_value={
                "id": 7,
                "name": "USD main",
                "currency": "USD",
                "cash_balance": "100000.0000",
                "initial_balance": "100000.0000",
                "equity": "101230.0000",
                "total_return": "1230.0000",
                "total_return_pct": 1.23,
                "positions": [],
            }
        )
        out = asyncio.run(
            reg._get_sim_portfolio(db, user_id="00000000-0000-0000-0000-000000000099", account_id=7)
        )
    assert out["id"] == 7
    assert out["equity"] == "101230.0000"
    assert svc.get_account.await_count == 1
    # get_account(self, db, uid, account_id, for_update=False) — args[1] is the
    # caller's UUID (keycloak scope), args[2] is the requested account_id.
    call_args = svc.get_account.await_args
    assert str(call_args.args[1]) == "00000000-0000-0000-0000-000000000099"
    assert call_args.args[2] == 7


def test_get_sim_portfolio_specific_account_other_user_returns_error():
    """Owner-scoping negative: account belongs to someone else → error, no value."""
    reg = _reg()
    db = MagicMock()
    with patch("api.services.tool_registry.sim_service") as svc:
        svc.get_account = AsyncMock(return_value=None)  # get_account scopes by keycloak_id
        out = asyncio.run(
            reg._get_sim_portfolio(
                db, user_id="11111111-1111-1111-1111-111111111111", account_id=42
            )
        )
    assert "error" in out
    assert "42" in out["error"]
    assert "accounts" in out
    assert out["accounts"] == []


def test_get_sim_portfolio_no_accounts_returns_helpful_note():
    reg = _reg()
    db = MagicMock()
    with patch("api.services.tool_registry.sim_service") as svc:
        svc.list_accounts = AsyncMock(return_value=[])
        # Explicitly seed an AsyncMock so we can assert the await_count.
        svc.latest_prices = AsyncMock(return_value={})
        out = asyncio.run(
            reg._get_sim_portfolio(
                db, user_id="22222222-2222-2222-2222-222222222222", account_id=None
            )
        )
    assert out["accounts"] == []
    assert "simulator" in out["note"].lower()
    # With zero accounts, the handler short-circuits before fetching prices.
    assert svc.latest_prices.await_count == 0


def test_get_sim_portfolio_list_summary_excludes_other_users_accounts():
    """list_accounts is owner-scoped in sim_service — we trust that boundary,
    but assert our handler doesn't bypass it."""
    from decimal import Decimal

    reg = _reg()
    db = MagicMock()
    user_a_acct = _account(11, "A USD", cash=Decimal("90000"), initial=Decimal("100000"))
    user_a_acct.keycloak_id = "33333333-3333-3333-3333-333333333333"

    async def fake_execute(stmt):
        # Position query returns nothing (no holdings)
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))

    db.execute = fake_execute
    with patch("api.services.tool_registry.sim_service") as svc:
        svc.list_accounts = AsyncMock(return_value=[user_a_acct])  # already owner-scoped
        svc.latest_prices = AsyncMock(return_value={})
        out = asyncio.run(
            reg._get_sim_portfolio(
                db, user_id="33333333-3333-3333-3333-333333333333", account_id=None
            )
        )
    assert len(out["accounts"]) == 1
    assert out["accounts"][0]["id"] == 11
    assert out["accounts"][0]["name"] == "A USD"
    assert out["accounts"][0]["position_count"] == 0
    assert out["accounts"][0]["equity"] == "90000.0000"  # cash + 0 positions
    # Caller asked for one user; we only ever passed that user's id to list_accounts.
    list_args = svc.list_accounts.await_args
    assert str(list_args.args[1]) == "33333333-3333-3333-3333-333333333333"
