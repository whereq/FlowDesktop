"""Trust layer — provenance extraction from tool results (pure, no DB/LLM)."""

import json

from api.services.llm_gateway import _provenance_from_result


def test_extracts_source_and_as_of_from_timestamp():
    content = json.dumps({"symbol": "AAPL", "price": 200, "timestamp": "2026-06-30T14:32:00"})
    p = _provenance_from_result("get_stock_quote", content)
    assert p == {"tool": "get_stock_quote", "as_of": "2026-06-30T14:32:00", "symbol": "AAPL"}


def test_prefers_as_of_over_timestamp_over_date():
    content = json.dumps({"as_of": "A", "timestamp": "B", "date": "C", "source": "FRED"})
    p = _provenance_from_result("get_macro_indicators", content)
    assert p["as_of"] == "A" and p["source"] == "FRED"


def test_date_only_fallback():
    content = json.dumps({"date": "2026-06-29"})
    assert _provenance_from_result("get_price_history", content)["as_of"] == "2026-06-29"


def test_no_provenance_fields_yields_bare_tool():
    assert _provenance_from_result("get_watchlist", json.dumps({"items": []})) == {
        "tool": "get_watchlist"
    }


def test_list_result_is_handled():
    assert _provenance_from_result("get_market_movers", json.dumps([1, 2, 3])) == {
        "tool": "get_market_movers"
    }


def test_invalid_json_yields_bare_tool():
    assert _provenance_from_result("web_fetch", "not json") == {"tool": "web_fetch"}


def test_none_content_yields_bare_tool():
    assert _provenance_from_result("x", None) == {"tool": "x"}
