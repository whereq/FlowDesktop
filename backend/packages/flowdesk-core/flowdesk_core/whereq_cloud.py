"""Client for the whereq.cloud Data API.

FlowDesktop is a **client** of the whereq.cloud data cloud: every piece of
market data it shows comes from the Data API, and every call is made with the
operator's API key. There is no anonymous path and no bundled scraper — the
key is what turns the data on.

Authentication
--------------
The key is sent in the ``X-API-Key`` header (the API also accepts
``Authorization: Bearer``). Keys are issued per account and may carry scopes;
a key with the ``filings`` scope is required for the SEC endpoints.

Endpoints used here
-------------------
=============================  =========================================
``/v1/stats``                  dataset counters
``/v1/catalog``                exchange coverage (market + currency)
``/v1/catalog/symbols``        the symbol universe (paginated)
``/v1/catalog/symbol/{sym}``   one symbol's profile
``/v1/equities/{sym}/quote``   the latest quote
``/v1/equities/quotes``        quotes for a batch of symbols
``/v1/equities/{sym}/history`` daily OHLCV history
``/v1/alt/short-interest/{sym}``  short-interest history
``/v1/alt/insider/{sym}``      Form 4 insider transactions
``/v1/edgar/filings``          SEC filing metadata (needs ``filings`` scope)
=============================  =========================================
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger("flowdesk-core.whereq-cloud")

#: The public Data API. Override with ``WHEREQ_API_URL`` for a self-hosted
#: or regional deployment.
DEFAULT_BASE_URL = "https://api.whereq.cloud"

#: How long to wait for the API before giving up, in seconds.
DEFAULT_TIMEOUT = 30.0

#: Retries on a transient failure (5xx, 429, network error).
MAX_RETRIES = 3

#: The API accepts at most 50 symbols per ``/v1/equities/quotes`` request.
MAX_QUOTE_SYMBOLS = 50

#: The API accepts at most 2000 daily bars per history request.
MAX_HISTORY_LIMIT = 2000

#: The API accepts at most 10000 catalog rows per page.
MAX_CATALOG_LIMIT = 10000


class WhereqCloudError(RuntimeError):
    """Raised when the whereq.cloud API cannot be used.

    ``status_code`` is the HTTP status when the API answered, or ``None`` for
    a transport failure.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WhereqCloudAuthError(WhereqCloudError):
    """The API rejected the key (401/403), or no key was configured."""


class WhereqCloudClient:
    """A thin async client over the whereq.cloud Data API.

    The key is required. A client built without one refuses every call with
    :class:`WhereqCloudAuthError` — the application must not silently fall
    back to anonymous access.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        from flowdesk_core.config import get_settings

        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.whereq_api_key or "").strip()
        self.base_url = (base_url or settings.whereq_api_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.whereq_api_timeout
        self._client = client
        self._owns_client = client is None

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise WhereqCloudAuthError(
                "No whereq.cloud API key configured. Set WHEREQ_API_KEY in your "
                "environment (or backend/.env). FlowDesktop reads market data "
                "from the whereq.cloud Data API and cannot run without a key."
            )
        return {
            "X-API-Key": self.api_key,
            "User-Agent": "FlowDesktop/1.0",
            "Accept": "application/json",
        }

    def require_key(self) -> str:
        """Assert a key is configured and return it.

        Every request goes through :meth:`_headers`, which raises when no key
        is set — there is no anonymous path.
        """
        if not self.api_key:
            raise WhereqCloudAuthError(
                "No whereq.cloud API key configured. Set WHEREQ_API_KEY in your "
                "environment (or backend/.env). FlowDesktop reads market data "
                "from the whereq.cloud Data API and cannot run without a key."
            )
        return self.api_key

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._headers(),
            )
        return self._client

    async def get(self, path: str, **params: Any) -> dict:
        """GET ``path`` and return the decoded JSON body.

        Raises :class:`WhereqCloudError` on a non-2xx response or a transport
        failure. Transient failures are retried a few times.
        """
        # The header is set per request, not only on the client, so the key is
        # sent even when an HTTP client was injected from the outside.
        headers = self._headers()
        client = await self._get_client()
        url = path if path.startswith("/") else f"/{path}"
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.get(url, headers=headers, params=params or None)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == MAX_RETRIES:
                    break
                logger.warning(
                    "whereq.cloud request failed (%s), retrying %d/%d",
                    exc,
                    attempt,
                    MAX_RETRIES,
                )
                await _sleep(1.0 * attempt)
                continue

            if response.status_code in (401, 403):
                raise WhereqCloudAuthError(
                    f"whereq.cloud rejected the API key ({response.status_code}) "
                    f"for {url}. Check WHEREQ_API_KEY and that the key grants the "
                    f"required scope.",
                    status_code=response.status_code,
                )

            if response.status_code == 429:
                if attempt == MAX_RETRIES:
                    raise WhereqCloudError(
                        f"whereq.cloud rate limit reached for {url}",
                        status_code=429,
                    )
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after or "").isdigit() else 1.5 * attempt
                logger.warning("whereq.cloud rate limited, sleeping %.1fs", delay)
                await _sleep(delay)
                continue

            if response.status_code >= 500:
                last_error = WhereqCloudError(
                    f"whereq.cloud server error {response.status_code} for {url}",
                    status_code=response.status_code,
                )
                if attempt == MAX_RETRIES:
                    break
                await _sleep(1.0 * attempt)
                continue

            if response.status_code >= 400:
                raise WhereqCloudError(
                    f"whereq.cloud returned {response.status_code} for {url}: "
                    f"{response.text[:200]}",
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except ValueError as exc:
                raise WhereqCloudError(f"whereq.cloud returned a non-JSON body for {url}") from exc

        raise WhereqCloudError(
            f"whereq.cloud request to {url} failed after {MAX_RETRIES} attempts: {last_error}"
        )

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> WhereqCloudClient:
        await self._get_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    async def stats(self) -> dict:
        """Dataset counters — instrument, quote and bar totals."""
        return await self.get("/v1/stats")

    async def exchanges(self) -> list[dict]:
        """One entry per covered exchange: code, market, currency, count."""
        payload = await self.get("/v1/catalog")
        return _as_rows(payload.get("exchanges"), "data")

    async def symbols_page(
        self,
        *,
        exchange: str | None = None,
        sector: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> tuple[int, list[dict]]:
        """One page of the symbol universe.

        Returns ``(total, rows)`` — ``total`` is the size of the whole
        matching set, so the caller can page through it.
        """
        limit = max(1, min(int(limit), MAX_CATALOG_LIMIT))
        params: dict[str, Any] = {"limit": limit, "offset": max(0, int(offset))}
        if exchange:
            params["exchange"] = exchange.strip().upper()
        if sector:
            params["sector"] = sector.strip()
        payload = await self.get("/v1/catalog/symbols", **params)
        total = int(payload.get("total") or 0)
        return total, _as_rows(payload, "data")

    async def symbols(self, **params: Any) -> list[dict]:
        """One page of the symbol universe (rows only)."""
        _total, rows = await self.symbols_page(**params)
        return rows

    async def symbol(self, symbol: str) -> dict:
        """One symbol's profile: name, exchange, sector, market cap, coverage."""
        return await self.get(f"/v1/catalog/symbol/{_sym(symbol)}")

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    async def quote(self, symbol: str) -> dict | None:
        """The latest quote for one symbol, or ``None`` when there is none."""
        payload = await self.get(f"/v1/equities/{_sym(symbol)}/quote")
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    async def quotes(self, symbols: list[str]) -> list[dict]:
        """Quotes for a batch of symbols (the API caps a request at 50)."""
        wanted = [s.strip().upper() for s in symbols if s and s.strip()][:MAX_QUOTE_SYMBOLS]
        if not wanted:
            return []
        payload = await self.get("/v1/equities/quotes", symbols=",".join(wanted))
        return _as_rows(payload, "data")

    async def history(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Daily OHLCV history for one symbol, newest row first."""
        params: dict[str, Any] = {}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()
        if limit:
            params["limit"] = max(1, min(int(limit), MAX_HISTORY_LIMIT))
        payload = await self.get(f"/v1/equities/{_sym(symbol)}/history", **params)
        return _as_rows(payload, "data")

    # ------------------------------------------------------------------
    # Alternative data
    # ------------------------------------------------------------------

    async def short_interest(self, symbol: str) -> list[dict]:
        """Short-interest history for one symbol, newest settlement first."""
        payload = await self.get(f"/v1/alt/short-interest/{_sym(symbol)}")
        return _as_rows(payload, "history")

    async def insider_transactions(
        self, symbol: str, days: int = 365, limit: int = 100
    ) -> list[dict]:
        """Form 4 insider transactions for one symbol, newest first."""
        payload = await self.get(
            f"/v1/alt/insider/{_sym(symbol)}",
            days=max(1, min(int(days), 3650)),
            limit=max(1, min(int(limit), 500)),
        )
        return _as_rows(payload, "transactions")

    async def filings(
        self,
        cik: str,
        form: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Recent SEC filings for an issuer.

        Requires an API key with the ``filings`` scope. The API returns
        filing-level metadata (form, dates, accession, document URL) — the
        document narrative itself is not part of this response.
        """
        params: dict[str, Any] = {"cik": str(cik), "limit": max(1, min(int(limit), 200))}
        if form:
            params["form"] = form
        if since:
            params["since"] = since
        payload = await self.get("/v1/edgar/filings", **params)
        return _as_rows(payload, "filings")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sym(symbol: str) -> str:
    """Normalise a ticker for use in a URL path."""
    return (symbol or "").strip().upper()


def _as_rows(payload: Any, key: str) -> list[dict]:
    """Pull a list of rows out of an API response.

    The API returns either ``{"data": [...]}`` or a named list depending on
    the endpoint, and some endpoints return a bare list.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for candidate in (key, "data", "rows", "results", "items"):
        value = payload.get(candidate)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
