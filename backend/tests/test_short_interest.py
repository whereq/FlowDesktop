"""Short interest — the Data API mapping and the NOVA read-side payload.

The yfinance parser is gone: short-interest snapshots are synced from the
whereq.cloud Data API, which returns rows already in the FINRA shape the
table uses. The payload → ORM mapping is covered in
``test_collector_mapping.py``; this file covers the read side.
"""

from datetime import date

from api.services.tool_registry import _short_interest_payload
from flowdesk_core.models.short_interest import ShortInterest

# ---------------------------------------------------------------------------
# Write side: Data API payload -> ORM columns
# ---------------------------------------------------------------------------


def _api_payload():
    return {
        "settlement_date": "2026-10-15",
        "short_interest": 131591865,
        "prior_short_interest": 128753092,
        "avg_daily_volume": 42880493,
        "days_to_cover": 3.48,
        "short_pct_of_float": 0.0091,
        "change_pct": 2.2,
        "source": "Yahoo Finance",
    }


def test_api_payload_maps_onto_the_orm_columns():
    from flowdesk_collector.collectors.mapping import short_interest_values

    v = short_interest_values(_api_payload())
    assert v["settlement_date"] == date(2026, 10, 15)
    assert v["short_interest"] == 131591865
    assert v["prior_short_interest"] == 128753092
    assert v["avg_daily_volume"] == 42880493
    assert v["days_to_cover"] == 3.48
    assert v["short_pct_of_float"] == 0.0091
    assert v["change_pct"] == 2.2


def test_row_keys_are_real_orm_columns():
    """Guards the regression: every key must exist on the ShortInterest model."""
    from flowdesk_collector.collectors.mapping import short_interest_values

    v = short_interest_values(_api_payload())
    orm_cols = {c.name for c in ShortInterest.__table__.columns}
    assert set(v) <= orm_cols, set(v) - orm_cols


def test_row_is_dropped_without_a_share_count():
    """`short_interest` is NOT NULL — a row without it says nothing."""
    from flowdesk_collector.collectors.mapping import short_interest_values

    payload = _api_payload()
    payload["short_interest"] = None
    assert short_interest_values(payload) is None


# ---------------------------------------------------------------------------
# Read side: ORM row -> API payload
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
