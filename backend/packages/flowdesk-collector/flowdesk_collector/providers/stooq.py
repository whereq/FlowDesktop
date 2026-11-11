"""Stooq CSV scraping provider (historical data only)."""

import asyncio
import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal

import aiohttp

from flowdesk_collector.providers.base import (
    ADJUSTMENT_NONE,
    BaseProvider,
    HistoricalData,
    ProviderRateLimitedError,
    QuoteData,
    StockInfo,
)

logger = logging.getLogger(__name__)

# Stooq exchange suffix map
_EXCHANGE_SUFFIX = {
    "NYSE": ".us",
    "NASDAQ": ".us",
    "TSX": ".ca",
}


def _to_stooq_symbol(symbol: str, exchange: str) -> str:
    """Convert Yahoo Finance symbol format to Stooq format.

    NYSE/NASDAQ: AAPL -> aapl.us
    TSX: RY.TO -> ry.ca  (strip .TO suffix, lowercase, add .ca)
    """
    ticker = symbol.upper()
    # Strip the .TO suffix if present
    if exchange == "TSX" and ticker.endswith(".TO"):
        ticker = ticker[:-3]
    suffix = _EXCHANGE_SUFFIX.get(exchange, ".us")
    return (ticker + suffix).lower()


class StooqProvider(BaseProvider):
    """Stooq CSV scraping provider.

    Free, no API key required.
    Historical data only (no real-time).
    Requires 2+ second politeness delay between requests.
    Supports NYSE, NASDAQ, and TSX.

    IMPORTANT: This provider scrapes CSV files. A minimum 2-second delay
    must be observed between consecutive requests to respect the host.
    """

    name = "stooq"
    priority = 8
    daily_limit = None  # No explicit limit but must be polite
    minute_limit = 20  # Self-imposed: ~2s delay = max ~30/min, use 20 to be safe
    supports_batch = False  # Must request one symbol at a time
    supported_exchanges = ["NYSE", "NASDAQ", "TSX"]
    supports_realtime = False  # Historical CSV only
    supports_historical = True

    BASE_URL = "https://stooq.com/q/d/l/"

    # Tracks the exchange for each symbol so we can convert the symbol format.
    # This mapping is populated by the orchestrator / work planner.
    _exchange_map: dict[str, str] = {}

    @classmethod
    def register_exchange(cls, symbol: str, exchange: str) -> None:
        """Register exchange context for a symbol (called from symbol_registry)."""
        cls._exchange_map[symbol] = exchange

    def _resolve_stooq_symbol(self, symbol: str) -> str:
        """Convert symbol to Stooq format using registered exchange context."""
        exchange = self._exchange_map.get(symbol, "NYSE")
        return _to_stooq_symbol(symbol, exchange)

    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Stooq does not provide real-time quotes; return None."""
        return None

    async def get_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        """Stooq does not provide real-time quotes; return empty list."""
        return []

    async def get_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        """Fetch historical CSV data for a symbol from Stooq."""
        stooq_sym = self._resolve_stooq_symbol(symbol)
        d1 = start_date.strftime("%Y%m%d")
        d2 = end_date.strftime("%Y%m%d")

        url = self.BASE_URL
        params = {"s": stooq_sym, "d1": d1, "d2": d2, "i": "d"}

        try:
            timeout = aiohttp.ClientTimeout(total=12)  # fail fast if IP is blocked
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(url, params=params) as response,
            ):
                if response.status != 200:
                    logger.warning(f"Stooq returned {response.status} for {stooq_sym}")
                    return []

                response.headers.get("Content-Type", "")
                raw = await response.text()

                # Stooq returns "No data" text when symbol not found
                if not raw or raw.strip().startswith("No") or "<html" in raw.lower():
                    logger.debug(f"Stooq: no CSV data for {stooq_sym}")
                    return []

        except (TimeoutError, aiohttp.ClientError) as exc:
            logger.warning(
                "Stooq connection failed, disabling provider",
                extra={
                    "operation": "historical_fetch",
                    "provider": "stooq",
                    "symbol": symbol,
                    "error_type": "connection_error",
                },
            )
            raise ProviderRateLimitedError(f"Stooq connection failed: {exc}")
        except Exception:
            logger.error(
                "Stooq historical fetch failed",
                extra={
                    "operation": "historical_fetch",
                    "provider": "stooq",
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
            return []

        # Parse CSV: Date,Open,High,Low,Close,Volume
        historical: list[HistoricalData] = []
        try:
            reader = csv.DictReader(io.StringIO(raw))
            for row in reader:
                try:
                    d = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                    close_str = row.get("Close", "")
                    if not close_str:
                        continue
                    close = Decimal(close_str)
                    historical.append(
                        HistoricalData(
                            symbol=symbol,
                            date=d,
                            open_price=(Decimal(row["Open"]) if row.get("Open") else None),
                            high=Decimal(row["High"]) if row.get("High") else None,
                            low=Decimal(row["Low"]) if row.get("Low") else None,
                            close=close,
                            adj_close=close,
                            adjustment=ADJUSTMENT_NONE,
                            volume=int(row["Volume"]) if row.get("Volume") else None,
                            provider=self.name,
                        )
                    )
                except (ValueError, KeyError) as exc:
                    logger.debug(f"Stooq CSV parse error for {symbol}: {exc}")
                    continue
        except Exception:
            logger.error(
                "CSV reader error",
                extra={
                    "operation": "historical_fetch",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "parse_error",
                },
            )
            return []

        # Mandatory 2-second politeness delay before next request
        await asyncio.sleep(2.0)

        return sorted(historical, key=lambda x: x.date)

    async def get_stock_info(self, symbol: str) -> StockInfo | None:
        """Stooq does not provide metadata; return None."""
        return None

    async def search_stocks(self, query: str) -> list[StockInfo]:
        """Stooq does not have a search API; return empty list."""
        return []
