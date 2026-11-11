"""Per-market trading rules for the simulator (data-driven, extensible).

Keyed by account currency. v1 enforces `lot` (board-lot size) + the tradable
universe; `settlement` and `price_limit_pct` are hooks used from Phase 2 (CN T+1,
±10% daily limit). Adding a market is a one-line addition here.
See docs/design/RFC_STOCK_TRADING_SIMULATOR.md §7.6.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRules:
    lot: int = 1  # board-lot size (US=1, CN=100)
    fractional: bool = False  # allow fractional shares
    settlement: str = "T+2"  # informational v1; CN T+1 sell-restriction is Phase 2
    price_limit_pct: float | None = None  # daily price limit (CN ±10%); Phase 2


MARKET_RULES: dict[str, MarketRules] = {
    "USD": MarketRules(lot=1, settlement="T+2"),
    "CAD": MarketRules(lot=1, settlement="T+2"),
    "HKD": MarketRules(lot=1, settlement="T+2"),  # HK lots vary by name; simplify to 1 for v1
    "CNY": MarketRules(lot=100, settlement="T+1", price_limit_pct=10.0),
    "JPY": MarketRules(lot=100, settlement="T+2"),
    "SGD": MarketRules(lot=100, settlement="T+2"),
    "TWD": MarketRules(lot=1000, settlement="T+2", price_limit_pct=10.0),
    "KRW": MarketRules(lot=1, settlement="T+2", price_limit_pct=30.0),
}

_DEFAULT = MarketRules()


def rules_for(currency: str | None) -> MarketRules:
    return MARKET_RULES.get((currency or "").upper(), _DEFAULT)
