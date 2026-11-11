"""Data API payload → ORM row mappings (pure, no network/DB).

Every mapping is checked against the real ORM column names — a key that does
not exist on the model would only blow up at write time in production.
"""

from datetime import date, datetime
from decimal import Decimal

from flowdesk_collector.collectors.mapping import (
    history_values,
    insider_values,
    quote_values,
    short_interest_values,
    to_date,
    to_datetime,
    to_decimal,
    to_float,
    to_int,
)
from flowdesk_core.models.historical import HistoricalPrice
from flowdesk_core.models.insider_transaction import InsiderTransaction
from flowdesk_core.models.quote import Quote
from flowdesk_core.models.short_interest import ShortInterest

# ---------------------------------------------------------------------------
# Scalar coercion
# ---------------------------------------------------------------------------


def test_to_decimal_handles_strings_numbers_and_junk():
    assert to_decimal("1.25") == Decimal("1.25")
    assert to_decimal(2) == Decimal("2")
    assert to_decimal(None) is None
    assert to_decimal("") is None
    assert to_decimal("not a number") is None


def test_to_int_and_to_float():
    assert to_int("42") == 42
    assert to_int("42.9") == 42
    assert to_int(None) is None
    assert to_float("0.0525") == 0.0525
    assert to_float("") is None


def test_to_date():
    assert to_date("2026-06-15") == date(2026, 6, 15)
    assert to_date("2026-06-15T10:00:00") == date(2026, 6, 15)
    assert to_date(None) is None
    assert to_date("garbage") is None


def test_to_datetime_converts_an_aware_timestamp_to_utc():
    aware = "2026-06-15T12:00:00+02:00"
    assert to_datetime(aware) == datetime(2026, 6, 15, 10, 0, 0)


def test_to_datetime_keeps_a_naive_timestamp_as_is():
    assert to_datetime("2026-06-15T12:00:00") == datetime(2026, 6, 15, 12, 0, 0)
    assert to_datetime(None) is None
    assert to_datetime("nope") is None


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------

QUOTE = {
    "symbol": "AAPL",
    "price": 347.96,
    "open_price": 350.675,
    "high": 353.87,
    "low": 346.4605,
    "close": 350.69,
    "volume": None,
    "change": -2.73,
    "change_percent": -0.7785,
    "provider": "finnhub",
    "timestamp": "2026-11-10T18:49:13.717981",
}


def test_quote_maps_the_api_payload():
    v = quote_values(QUOTE)
    assert v["price"] == Decimal("347.96")
    assert v["open_price"] == Decimal("350.675")
    assert v["high"] == Decimal("353.87")
    assert v["low"] == Decimal("346.4605")
    assert v["close"] == Decimal("350.69")
    assert v["volume"] is None
    assert v["change"] == Decimal("-2.73")
    assert v["change_percent"] == Decimal("-0.7785")
    assert v["provider"] == "finnhub"
    assert v["timestamp"] == datetime(2026, 11, 10, 18, 49, 13, 717981)


def test_quote_keys_are_real_orm_columns():
    v = quote_values(QUOTE)
    orm_cols = {c.name for c in Quote.__table__.columns}
    assert set(v) <= orm_cols, set(v) - orm_cols


def test_quote_without_a_price_is_dropped():
    """A quote with no price says nothing — `price` is NOT NULL."""
    assert quote_values({"symbol": "AAPL"}) is None


def test_quote_defaults_the_provider_label():
    v = quote_values({"price": 1.0})
    assert v["provider"] == "whereq_cloud"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

BAR = {
    "date": "2026-11-05",
    "open_price": 353.89,
    "high": 355.38,
    "low": 342.06,
    "close": 344.17,
    "adj_close": 344.17,
    "volume": 75678900,
    "provider": "yahoo_finance",
    "adjustment": "split_dividend_adjusted",
}


def test_history_maps_the_api_payload():
    v = history_values(BAR)
    assert v["date"] == date(2026, 11, 5)
    assert v["close"] == Decimal("344.17")
    assert v["adj_close"] == Decimal("344.17")
    assert v["volume"] == 75678900
    assert v["provider"] == "yahoo_finance"
    assert v["adjustment"] == "split_dividend_adjusted"


def test_history_keys_are_real_orm_columns():
    v = history_values(BAR)
    orm_cols = {c.name for c in HistoricalPrice.__table__.columns}
    assert set(v) <= orm_cols, set(v) - orm_cols


def test_history_without_a_date_is_dropped():
    assert history_values({"close": 1.0}) is None


# ---------------------------------------------------------------------------
# Short interest
# ---------------------------------------------------------------------------

SHORT = {
    "settlement_date": "2026-10-15",
    "short_interest": 131591865,
    "avg_daily_volume": 42880493,
    "days_to_cover": 3.48,
    "short_pct_of_float": 0.0091,
    "prior_short_interest": 128753092,
    "change_pct": 2.2,
    "source": "Yahoo Finance",
}


def test_short_interest_maps_the_api_payload():
    v = short_interest_values(SHORT)
    assert v["settlement_date"] == date(2026, 10, 15)
    assert v["short_interest"] == 131591865
    assert v["prior_short_interest"] == 128753092
    assert v["avg_daily_volume"] == 42880493
    assert v["days_to_cover"] == 3.48
    assert v["short_pct_of_float"] == 0.0091
    assert v["change_pct"] == 2.2
    assert v["source"] == "Yahoo Finance"


def test_short_interest_keys_are_real_orm_columns():
    v = short_interest_values(SHORT)
    orm_cols = {c.name for c in ShortInterest.__table__.columns}
    assert set(v) <= orm_cols, set(v) - orm_cols


def test_short_interest_without_a_share_count_is_dropped():
    """`short_interest` is NOT NULL — a row without it says nothing."""
    assert short_interest_values({"settlement_date": "2026-10-15"}) is None


def test_short_interest_without_a_settlement_date_is_dropped():
    assert short_interest_values({"short_interest": 5}) is None


# ---------------------------------------------------------------------------
# Insider transactions
# ---------------------------------------------------------------------------

TXN = {
    "id": 2485,
    "insider_name": "Newstead Jennifer",
    "insider_title": "SVP, GC and Government Affairs",
    "transaction_date": "2026-11-03",
    "transaction_code": "S",
    "acquired_disposed": "D",
    "shares": "2399.0000",
    "price_per_share": "325.7500",
    "total_value": "781474.25",
    "shares_owned_after": "29997.0000",
    "filing_date": "2026-11-05",
    "accession": "0001140361-26-042149",
    "source": "SEC EDGAR Form 4",
}


def test_insider_maps_the_api_payload():
    v = insider_values(TXN)
    assert v["accession"] == "0001140361-26-042149"
    assert v["insider_name"] == "Newstead Jennifer"
    assert v["insider_title"] == "SVP, GC and Government Affairs"
    assert v["transaction_date"] == date(2026, 11, 3)
    assert v["filing_date"] == date(2026, 11, 5)
    assert v["transaction_code"] == "S"
    assert v["acquired_disposed"] == "D"
    assert v["shares"] == Decimal("2399.0000")
    assert v["price"] == Decimal("325.7500")
    assert v["value"] == Decimal("781474.25")
    assert v["shares_owned_after"] == Decimal("29997.0000")


def test_insider_uses_the_api_id_as_the_line_index():
    """The stable platform id is what keeps (accession, line_index) unique."""
    assert insider_values(TXN)["line_index"] == 2485


def test_insider_keys_are_real_orm_columns():
    v = insider_values(TXN)
    orm_cols = {c.name for c in InsiderTransaction.__table__.columns}
    assert set(v) <= orm_cols, set(v) - orm_cols


def test_insider_without_an_accession_or_name_is_dropped():
    assert insider_values({"id": 1, "insider_name": "X"}) is None
    assert insider_values({"id": 1, "accession": "X"}) is None


def test_insider_without_an_id_falls_back_to_line_index_zero():
    row = {k: v for k, v in TXN.items() if k != "id"}
    assert insider_values(row)["line_index"] == 0


def test_insider_flags_default_to_false():
    """The API exposes the insider's title, not their role flags."""
    v = insider_values(TXN)
    assert v["is_director"] is False
    assert v["is_officer"] is False
    assert v["is_ten_pct"] is False


def test_insider_does_not_claim_a_cik():
    """The API addresses insider activity by ticker — there is no CIK to store."""
    v = insider_values(TXN)
    assert "cik" not in v
    assert InsiderTransaction.__table__.columns["cik"].nullable
