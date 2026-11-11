"""Financial Modeling Prep (FMP) data provider.

Free tier: 250 requests/day, 5 requests/minute.
Supports US stocks (NYSE, NASDAQ) — quotes, historical, fundamentals.
API key required (free registration at https://financialmodelingprep.com/).
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import aiohttp

from flowdesk_collector.providers.base import (
    ADJUSTMENT_SPLIT_DIVIDEND,
    BaseProvider,
    HistoricalData,
    QuoteData,
    StockInfo,
)
from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)


class FMPProvider(BaseProvider):
    """Financial Modeling Prep API provider.

    Free tier: 250 API calls/day, ~5 req/min.
    Supports NYSE and NASDAQ. Provides real-time quotes (15-min delayed),
    historical daily data, and company profiles.
    Good complement to Alpha Vantage (25/day) with 10x the quota.
    """

    name = "fmp"
    priority = 4  # Between Finnhub (3) and Polygon (5)
    daily_limit = 250
    minute_limit = 5
    supports_batch = True  # Batch quote endpoint supports up to 50 symbols
    supported_exchanges = ["NYSE", "NASDAQ"]
    supports_realtime = True
    supports_historical = True

    BASE_URL = "https://financialmodelingprep.com/api/v3"
    STABLE_URL = "https://financialmodelingprep.com/stable"  # calendar/newer endpoints

    def __init__(self):
        self.api_key = get_settings().fmp_api_key

    async def is_available(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)

    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Get current quote for a single symbol."""
        if not self.api_key:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/quote/{symbol}"
                params = {"apikey": self.api_key}

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    if not data or not isinstance(data, list) or len(data) == 0:
                        return None

                    item = data[0]
                    price = item.get("price")
                    if not price:
                        return None

                    return QuoteData(
                        symbol=symbol,
                        price=Decimal(str(price)),
                        open_price=Decimal(str(item["open"])) if item.get("open") else None,
                        high=Decimal(str(item["dayHigh"])) if item.get("dayHigh") else None,
                        low=Decimal(str(item["dayLow"])) if item.get("dayLow") else None,
                        close=Decimal(str(item["previousClose"]))
                        if item.get("previousClose")
                        else None,
                        volume=item.get("volume"),
                        change=Decimal(str(item["change"])) if item.get("change") else None,
                        change_percent=Decimal(str(item["changesPercentage"]))
                        if item.get("changesPercentage")
                        else None,
                        timestamp=datetime.fromtimestamp(item["timestamp"], tz=UTC)
                        if item.get("timestamp")
                        else datetime.now(UTC),
                        provider=self.name,
                    )

        except Exception as e:
            logger.debug(f"FMP quote error for {symbol}: {e}")
            return None

    async def get_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        """Get quotes for multiple symbols (up to 50 per call)."""
        if not self.api_key or not symbols:
            return []

        quotes: list[QuoteData] = []

        # FMP batch endpoint accepts comma-separated symbols (max ~50)
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            symbol_list = ",".join(batch)

            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.BASE_URL}/quote/{symbol_list}"
                    params = {"apikey": self.api_key}

                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            logger.warning(
                                "Batch quote fetch returned non-200 status",
                                extra={
                                    "operation": "batch_fetch",
                                    "provider": self.name,
                                    "error_type": "http_error",
                                },
                            )
                            continue

                        data = await response.json()
                        if not data or not isinstance(data, list):
                            continue

                        for item in data:
                            sym = item.get("symbol")
                            price = item.get("price")
                            if not sym or not price:
                                continue

                            quotes.append(
                                QuoteData(
                                    symbol=sym,
                                    price=Decimal(str(price)),
                                    open_price=Decimal(str(item["open"]))
                                    if item.get("open")
                                    else None,
                                    high=Decimal(str(item["dayHigh"]))
                                    if item.get("dayHigh")
                                    else None,
                                    low=Decimal(str(item["dayLow"]))
                                    if item.get("dayLow")
                                    else None,
                                    close=Decimal(str(item["previousClose"]))
                                    if item.get("previousClose")
                                    else None,
                                    volume=item.get("volume"),
                                    change=Decimal(str(item["change"]))
                                    if item.get("change")
                                    else None,
                                    change_percent=Decimal(str(item["changesPercentage"]))
                                    if item.get("changesPercentage")
                                    else None,
                                    timestamp=datetime.fromtimestamp(item["timestamp"], tz=UTC)
                                    if item.get("timestamp")
                                    else datetime.now(UTC),
                                    provider=self.name,
                                )
                            )

            except Exception:
                logger.warning(
                    "Batch quote fetch failed",
                    extra={
                        "operation": "batch_fetch",
                        "provider": self.name,
                        "error_type": "unknown_error",
                    },
                )
                continue

        return quotes

    async def get_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        """Get historical daily prices for a symbol."""
        if not self.api_key:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/historical-price-full/{symbol}"
                params = {
                    "apikey": self.api_key,
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                }

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    historical_data = data.get("historical", [])
                    if not historical_data:
                        return []

                    results: list[HistoricalData] = []
                    for item in historical_data:
                        try:
                            results.append(
                                HistoricalData(
                                    symbol=symbol,
                                    date=date.fromisoformat(item["date"]),
                                    open_price=Decimal(str(item["open"]))
                                    if item.get("open")
                                    else None,
                                    high=Decimal(str(item["high"])) if item.get("high") else None,
                                    low=Decimal(str(item["low"])) if item.get("low") else None,
                                    close=Decimal(str(item["close"]))
                                    if item.get("close")
                                    else None,
                                    adj_close=Decimal(str(item["adjClose"]))
                                    if item.get("adjClose")
                                    else None,
                                    adjustment=ADJUSTMENT_SPLIT_DIVIDEND,
                                    volume=item.get("volume"),
                                    provider=self.name,
                                )
                            )
                        except (ValueError, KeyError):
                            continue

                    return results

        except Exception:
            logger.warning(
                "Historical fetch failed",
                extra={
                    "operation": "historical_fetch",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
            return []

    async def get_stock_info(self, symbol: str) -> StockInfo | None:
        """Get company profile information."""
        if not self.api_key:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/profile/{symbol}"
                params = {"apikey": self.api_key}

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    if not data or not isinstance(data, list) or len(data) == 0:
                        return None

                    item = data[0]
                    return StockInfo(
                        symbol=symbol,
                        name=item.get("companyName", symbol),
                        exchange=item.get("exchangeShortName"),
                        sector=item.get("sector"),
                        industry=item.get("industry"),
                        market_cap=item.get("mktCap"),
                    )

        except Exception as e:
            logger.debug(f"FMP stock info error for {symbol}: {e}")
            return None

    async def search_stocks(self, query: str) -> list[StockInfo]:
        """Search for stocks by name or symbol."""
        if not self.api_key:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/search"
                params = {
                    "query": query,
                    "limit": 10,
                    "apikey": self.api_key,
                }

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    if not data:
                        return []

                    return [
                        StockInfo(
                            symbol=item.get("symbol", ""),
                            name=item.get("name", ""),
                            exchange=item.get("exchangeShortName"),
                        )
                        for item in data
                        if item.get("symbol")
                    ]

        except Exception as e:
            logger.debug(f"FMP search error for {query}: {e}")
            return []


# ---------------------------------------------------------------------------
# Calendar helpers (earnings + dividends) — bulk endpoints
# ---------------------------------------------------------------------------


def _cal_date(s):
    """Parse 'YYYY-MM-DD' (FMP date) → date, or None."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _cal_dec(v):
    """Parse a numeric → Decimal, or None (empty/invalid)."""
    if v in (None, "", 0) and v != 0:
        return None
    try:
        return Decimal(str(v))
    except (ValueError, TypeError, ArithmeticError):
        return None


async def _fmp_get_json(url: str, params: dict):
    async with (
        aiohttp.ClientSession() as session,
        session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp,
    ):
        if resp.status != 200:
            logger.warning("FMP calendar HTTP %s for %s", resp.status, url)
            return None
        return await resp.json()


async def fetch_earnings_calendar(from_date: date, to_date: date) -> list[dict]:
    """Bulk earnings calendar for a date window → normalized event dicts.

    One API call covers all US symbols in the window.
    """
    api_key = get_settings().fmp_api_key
    if not api_key:
        return []
    # FMP "stable" API (the /api/v3 calendar endpoints were retired Aug 2025).
    url = f"{FMPProvider.STABLE_URL}/earnings-calendar"
    params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "apikey": api_key}
    rows = await _fmp_get_json(url, params)
    if not isinstance(rows, list):
        return []

    out: list[dict] = []
    for r in rows:
        d = _cal_date(r.get("date"))
        sym = (r.get("symbol") or "").strip().upper()
        if not d or not sym:
            continue
        out.append(
            {
                "symbol": sym,
                "kind": "earnings",
                "event_date": d,
                "time_of_day": (r.get("time") or None),
                "eps_estimate": _cal_dec(r.get("epsEstimated")),
                "eps_actual": _cal_dec(r.get("epsActual")),
                "revenue_estimate": _cal_dec(r.get("revenueEstimated")),
                "revenue_actual": _cal_dec(r.get("revenueActual")),
                "fiscal_period": (
                    str(r.get("fiscalDateEnding"))[:16] if r.get("fiscalDateEnding") else None
                ),
                "provider": "fmp",
            }
        )
    return out


async def fetch_dividend_calendar(from_date: date, to_date: date) -> list[dict]:
    """Bulk dividend calendar for a date window → normalized event dicts.

    `event_date` is the ex-dividend date. One API call covers all US symbols.
    """
    api_key = get_settings().fmp_api_key
    if not api_key:
        return []
    url = f"{FMPProvider.STABLE_URL}/dividends-calendar"
    params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "apikey": api_key}
    rows = await _fmp_get_json(url, params)
    if not isinstance(rows, list):
        return []

    out: list[dict] = []
    for r in rows:
        ex = _cal_date(r.get("date"))
        sym = (r.get("symbol") or "").strip().upper()
        amt = _cal_dec(r.get("dividend") if r.get("dividend") is not None else r.get("adjDividend"))
        if not ex or not sym:
            continue
        out.append(
            {
                "symbol": sym,
                "kind": "dividend",
                "event_date": ex,
                "amount": amt,
                "currency": "USD",
                "record_date": _cal_date(r.get("recordDate")),
                "pay_date": _cal_date(r.get("paymentDate")),
                "frequency": (r.get("frequency") or None),
                "provider": "fmp",
            }
        )
    return out
