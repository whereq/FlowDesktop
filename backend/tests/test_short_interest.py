"""Short interest — pure parse of a yfinance `.info` dict (no network/DB).

Also covers the FlowDesktop-side mapping between the provider's Yahoo-shaped dict
and the platform's FINRA-shaped ShortInterest ORM columns (migration 155/212).
"""

from datetime import UTC, date, datetime

from api.services.lazy_market_data import _short_interest_row
from api.services.tool_registry import _short_interest_payload
from flowdesk_collector.providers.short_interest import _to_date, parse_short_interest
from flowdesk_core.models.short_interest import ShortInterest


def _ts(y, m, d):
    return int(datetime(y, m, d, tzinfo=UTC).timestamp())


def test_parse_full():
    info = {
        "sharesShort": 50_000_000,
        "sharesShortPriorMonth": 40_000_000,
        "shortRatio": 3.2,
        "shortPercentOfFloat": 0.0525,
        "sharesPercentSharesOut": 0.0480,
        "dateShortInterest": _ts(2026, 6, 15),
    }
    p = parse_short_interest(info)
    assert p["shares_short"] == 50_000_000 and p["shares_short_prior"] == 40_000_000
    assert p["short_ratio"] == 3.2 and p["short_pct_float"] == 0.0525
    assert p["short_pct_outstanding"] == 0.0480
    assert p["as_of_date"] == date(2026, 6, 15)


def test_parse_partial_still_returns():
    # Only short ratio present — still short data.
    p = parse_short_interest({"shortRatio": 1.5})
    assert p is not None and p["short_ratio"] == 1.5 and p["shares_short"] is None
    assert p["as_of_date"] is None  # no dateShortInterest → caller coalesces


def test_parse_no_short_data_returns_none():
    assert parse_short_interest({"marketCap": 123, "shortName": "X"}) is None
    assert parse_short_interest({}) is None
    assert parse_short_interest(None) is None


def test_to_date_handles_bad_values():
    assert _to_date(None) is None
    assert _to_date("nope") is None
    assert _to_date(_ts(2026, 1, 2)) == date(2026, 1, 2)


# ---------------------------------------------------------------------------
# FlowDesktop-side mapping: provider dict -> ORM columns  (write side)
# ---------------------------------------------------------------------------


def _provider_payload():
    return {
        "as_of_date": date(2026, 11, 7),
        "shares_short": 50_000_000,
        "shares_short_prior": 40_000_000,
        "short_ratio": 3.2,
        "short_pct_float": 0.0525,
        "short_pct_outstanding": 0.0480,
        "avg_daily_volume": 55_000_000,
    }


def test_row_maps_provider_keys_to_orm_columns():
    row = _short_interest_row("AAPL", _provider_payload())
    # The live table uses these names (migration 155/212).
    assert row["symbol"] == "AAPL"
    assert row["settlement_date"] == date(2026, 11, 7)
    assert row["short_interest"] == 50_000_000
    assert row["prior_short_interest"] == 40_000_000
    assert row["avg_daily_volume"] == 55_000_000
    assert row["days_to_cover"] == 3.2
    assert row["short_pct_of_float"] == 0.0525
    assert row["short_pct_of_outstanding"] == 0.0480
    assert row["source"] == "Yahoo Finance"


def test_row_keys_are_real_orm_columns():
    """Guards the regression: every key must exist on the ShortInterest model."""
    row = _short_interest_row("AAPL", _provider_payload())
    orm_cols = {c.name for c in ShortInterest.__table__.columns}
    assert set(row) <= orm_cols, set(row) - orm_cols


def test_row_computes_change_pct():
    row = _short_interest_row("AAPL", _provider_payload())
    assert row["change_pct"] == 25.0


def test_row_change_pct_none_without_prior():
    payload = _provider_payload()
    payload["shares_short_prior"] = None
    assert _short_interest_row("AAPL", payload)["change_pct"] is None


def test_row_returns_none_without_share_count():
    """`short_interest` is NOT NULL — a row without it says nothing."""
    payload = _provider_payload()
    payload["shares_short"] = None
    assert _short_interest_row("AAPL", payload) is None


def test_row_coalesces_missing_date_to_today():
    payload = _provider_payload()
    payload["as_of_date"] = None
    row = _short_interest_row("AAPL", payload, today=date(2026, 11, 8))
    assert row["settlement_date"] == date(2026, 11, 8)


# ---------------------------------------------------------------------------
# FlowDesktop-side mapping: ORM row -> API payload  (read side)
# ---------------------------------------------------------------------------


def _orm_row(**overrides):
    values = {
        "id": 1,
        "symbol": "AAPL",
        "settlement_date": date(2026, 11, 7),
        "short_interest": 50_000_000,
        "prior_short_interest": 40_000_000,
        "avg_daily_volume": 55_000_000,
        "days_to_cover": 3.2,
        "short_pct_of_float": 0.0525,
        "short_pct_of_outstanding": 0.0480,
        "change_pct": 25.0,
        "source": "Yahoo Finance",
    }
    values.update(overrides)
    return ShortInterest(**values)


def test_payload_reads_new_orm_column_names():
    payload = _short_interest_payload(_orm_row())
    assert payload["as_of"] == "2026-11-07"
    assert payload["shares_short"] == 50_000_000
    assert payload["shares_short_prior_month"] == 40_000_000
    assert payload["days_to_cover"] == 3.2
    assert payload["short_pct_float"] == 5.25  # fraction → percent
    assert payload["shares_short_change_pct"] == 25.0


def test_payload_keys_match_frontend_contract():
    """frontend/src/api/client.ts → ShortInterestData"""
    payload = _short_interest_payload(_orm_row())
    assert set(payload) == {
        "symbol",
        "as_of",
        "short_pct_float",
        "days_to_cover",
        "shares_short",
        "shares_short_prior_month",
        "shares_short_change_pct",
        "source",
    }


def test_payload_falls_back_to_recomputed_change_pct():
    payload = _short_interest_payload(_orm_row(change_pct=None))
    assert payload["shares_short_change_pct"] == 25.0


def test_payload_handles_null_optionals():
    payload = _short_interest_payload(
        _orm_row(
            prior_short_interest=None,
            days_to_cover=None,
            short_pct_of_float=None,
            change_pct=None,
        )
    )
    assert payload["shares_short_prior_month"] is None
    assert payload["days_to_cover"] is None
    assert payload["short_pct_float"] is None
    assert payload["shares_short_change_pct"] is None
