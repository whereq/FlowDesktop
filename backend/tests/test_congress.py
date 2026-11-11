"""Congressional trades — pure normalize helpers (no network/DB)."""

from datetime import date

from flowdesk_collector.providers.congress_trades import (
    _pdate,
    _txn_type,
    normalize_congress_row,
    normalize_fmp_row,
)


def test_normalize_senate_purchase():
    row = {
        "transaction_date": "2026-05-01",
        "ticker": "AAPL",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "senator": "Thomas H Tuberville",
        "disclosure_date": "2026-05-20",
    }
    n = normalize_congress_row(row, "senate")
    assert n["symbol"] == "AAPL" and n["chamber"] == "senate"
    assert n["politician"] == "Thomas H Tuberville"
    assert n["txn_type"] == "buy" and n["amount_range"] == "$1,001 - $15,000"
    assert n["transaction_date"] == date(2026, 5, 1)
    assert n["disclosure_date"] == date(2026, 5, 20)
    assert n["source"] == "senate-stock-watcher" and len(n["dedup_hash"]) == 40


def test_normalize_house_slashdate_and_sale():
    row = {
        "transaction_date": "05/01/2026",
        "ticker": "nvda",
        "type": "Sale (Partial)",
        "amount": "$15,001 - $50,000",
        "representative": "Nancy Pelosi",
        "disclosure_date": "05/20/2026",
    }
    n = normalize_congress_row(row, "house")
    assert n["symbol"] == "NVDA" and n["chamber"] == "house"
    assert n["politician"] == "Nancy Pelosi" and n["txn_type"] == "sell"
    assert n["transaction_date"] == date(2026, 5, 1)


def test_normalize_skips_no_ticker():
    assert normalize_congress_row({"ticker": "--", "senator": "X"}, "senate") is None
    assert normalize_congress_row({"ticker": "", "senator": "X"}, "senate") is None
    assert normalize_congress_row({"senator": "X"}, "senate") is None


def test_dedup_hash_stable_and_distinct():
    r = {
        "transaction_date": "2026-05-01",
        "ticker": "AAPL",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "senator": "A B",
    }
    h1 = normalize_congress_row(dict(r), "senate")["dedup_hash"]
    h2 = normalize_congress_row(dict(r), "senate")["dedup_hash"]
    r2 = dict(r)
    r2["type"] = "Sale"
    h3 = normalize_congress_row(r2, "senate")["dedup_hash"]
    assert h1 == h2 and h1 != h3


def test_normalize_fmp_senate():
    row = {
        "symbol": "AAPL",
        "transactionDate": "2026-05-01",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "firstName": "Timothy",
        "lastName": "Tuberville",
        "disclosureDate": "2026-05-20",
        "office": "Tuberville, Thomas",
    }
    n = normalize_fmp_row(row, "senate")
    assert n["symbol"] == "AAPL" and n["politician"] == "Timothy Tuberville"
    assert n["txn_type"] == "buy" and n["source"] == "fmp-senate"
    assert n["transaction_date"] == date(2026, 5, 1)


def test_normalize_fmp_house_firstlast():
    # stable/house-latest carries firstName/lastName + office (no `representative`).
    row = {
        "symbol": "GOOGL",
        "transactionDate": "2026-06-15",
        "type": "Purchase",
        "amount": "$1,001 - $15,000",
        "firstName": "Cleo",
        "lastName": "Fields",
        "office": "Cleo Fields",
    }
    n = normalize_fmp_row(row, "house")
    assert n["symbol"] == "GOOGL" and n["politician"] == "Cleo Fields"
    assert n["txn_type"] == "buy" and n["source"] == "fmp-house"


def test_normalize_fmp_falls_back_to_office():
    row = {"symbol": "MSFT", "type": "Sale", "office": "Some Senator"}
    assert normalize_fmp_row(row, "senate")["politician"] == "Some Senator"


def test_normalize_fmp_skips_no_symbol():
    assert normalize_fmp_row({"type": "Purchase", "firstName": "A"}, "senate") is None


def test_txn_type_and_pdate():
    assert _txn_type("Purchase") == "buy" and _txn_type("purchase") == "buy"
    assert _txn_type("Sale (Full)") == "sell" and _txn_type("Exchange") == "exchange"
    assert _txn_type("weird") is None
    assert _pdate("2026-01-02") == date(2026, 1, 2)
    assert _pdate("01/02/2026") == date(2026, 1, 2)
    assert _pdate("garbage") is None and _pdate(None) is None
