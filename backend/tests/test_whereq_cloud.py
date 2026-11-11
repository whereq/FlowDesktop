"""whereq.cloud Data API client — key enforcement, transport, response shapes.

The client is exercised against ``httpx.MockTransport``, so the tests are
offline and deterministic while still going through the real request path.
"""

from datetime import date

import httpx
import pytest

from flowdesk_core.whereq_cloud import (
    MAX_QUOTE_SYMBOLS,
    WhereqCloudAuthError,
    WhereqCloudClient,
    WhereqCloudError,
)


def _client(handler, **kwargs):
    """Build a client whose transport is the given handler."""
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://api.whereq.cloud")
    return WhereqCloudClient(api_key="wq_test_key", client=http, **kwargs)


# ---------------------------------------------------------------------------
# The key requirement
# ---------------------------------------------------------------------------


async def test_no_key_refuses_every_call():
    """Without a key there is no anonymous path — not even a public endpoint."""
    client = WhereqCloudClient(api_key="")
    with pytest.raises(WhereqCloudAuthError) as exc:
        await client.stats()
    assert "WHEREQ_API_KEY" in str(exc.value)


async def test_no_key_refuses_even_with_an_injected_http_client():
    """An injected transport must not be a way around the key requirement."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    client = WhereqCloudClient(api_key="", client=http)
    with pytest.raises(WhereqCloudAuthError):
        await client.stats()


async def test_key_is_sent_in_the_x_api_key_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("X-API-Key")
        return httpx.Response(200, json={"instruments": 1})

    client = _client(handler)
    await client.stats()
    assert seen["key"] == "wq_test_key"
    await client.close()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


async def test_401_raises_an_auth_error():
    client = _client(lambda r: httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(WhereqCloudAuthError) as exc:
        await client.stats()
    assert exc.value.status_code == 401
    await client.close()


async def test_403_raises_an_auth_error():
    client = _client(lambda r: httpx.Response(403, json={"detail": "no scope"}))
    with pytest.raises(WhereqCloudAuthError):
        await client.stats()
    await client.close()


async def test_404_raises_a_plain_error():
    client = _client(lambda r: httpx.Response(404, json={"detail": "nope"}))
    with pytest.raises(WhereqCloudError) as exc:
        await client.symbol("NOPE")
    assert exc.value.status_code == 404
    await client.close()


async def test_500_is_retried_then_raised():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"detail": "boom"})

    client = _client(handler)
    with pytest.raises(WhereqCloudError):
        await client.stats()
    assert calls["n"] == 3  # MAX_RETRIES
    await client.close()


async def test_429_honours_retry_after(monkeypatch):
    calls = {"n": 0}
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("flowdesk_core.whereq_cloud._sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    assert await client.stats() == {"ok": True}
    assert calls["n"] == 2
    assert slept and slept[0] == 2.0
    await client.close()


async def test_non_json_body_raises():
    client = _client(lambda r: httpx.Response(200, text="<html>nope</html>"))
    with pytest.raises(WhereqCloudError):
        await client.stats()
    await client.close()


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------


async def test_symbols_page_returns_total_and_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/catalog/symbols"
        assert request.url.params["limit"] == "1000"
        assert request.url.params["offset"] == "2000"
        assert request.url.params["exchange"] == "NYSE"
        return httpx.Response(
            200,
            json={"total": 21900, "limit": 1000, "offset": 2000, "data": [{"symbol": "AAPL"}]},
        )

    client = _client(handler)
    total, rows = await client.symbols_page(exchange="NYSE", limit=1000, offset=2000)
    assert total == 21900
    assert rows == [{"symbol": "AAPL"}]
    await client.close()


async def test_quotes_caps_the_batch_at_fifty():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["symbols"] = request.url.params.get("symbols", "")
        return httpx.Response(200, json={"count": 0, "data": []})

    client = _client(handler)
    await client.quotes([f"S{i}" for i in range(80)])
    assert len(seen["symbols"].split(",")) == MAX_QUOTE_SYMBOLS
    await client.close()


async def test_quote_returns_none_when_the_api_has_no_quote():
    client = _client(
        lambda r: httpx.Response(200, json={"symbol": "AAPL", "data": None, "message": "no quote"})
    )
    assert await client.quote("AAPL") is None
    await client.close()


async def test_history_reads_the_data_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["start"] == "2026-01-01"
        assert request.url.params["limit"] == "250"
        return httpx.Response(
            200,
            json={"count": 1, "data": [{"date": "2026-01-02", "close": 10.0}]},
        )

    client = _client(handler)
    rows = await client.history("AAPL", start=date(2026, 1, 1), limit=250)
    assert rows == [{"date": "2026-01-02", "close": 10.0}]
    await client.close()


async def test_short_interest_reads_the_history_rows():
    client = _client(
        lambda r: httpx.Response(
            200, json={"symbol": "AAPL", "count": 1, "history": [{"short_interest": 5}]}
        )
    )
    assert await client.short_interest("AAPL") == [{"short_interest": 5}]
    await client.close()


async def test_insider_reads_the_transactions_rows():
    client = _client(
        lambda r: httpx.Response(
            200, json={"symbol": "AAPL", "count": 1, "transactions": [{"id": 1, "accession": "x"}]}
        )
    )
    assert await client.insider_transactions("AAPL") == [{"id": 1, "accession": "x"}]
    await client.close()


async def test_filings_requires_a_cik_and_sends_the_scope_checked_params():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["cik"] = request.url.params.get("cik")
        seen["form"] = request.url.params.get("form")
        return httpx.Response(200, json={"cik": "0000320193", "count": 0, "filings": []})

    client = _client(handler)
    await client.filings("320193", form="10-K")
    assert seen["cik"] == "320193"
    assert seen["form"] == "10-K"
    await client.close()


async def test_exchanges_reads_the_catalog_list():
    client = _client(
        lambda r: httpx.Response(
            200,
            json={"exchanges": [{"code": "NYSE", "market": "US", "currency": "USD"}]},
        )
    )
    assert await client.exchanges() == [{"code": "NYSE", "market": "US", "currency": "USD"}]
    await client.close()
