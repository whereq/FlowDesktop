"""Yahoo Finance data provider using yfinance library."""

import asyncio
import logging
import time
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from flowdesk_collector.providers._yahoo_exchange_base import YahooQuotaPool
from flowdesk_collector.providers.base import (
    ADJUSTMENT_SPLIT_DIVIDEND,
    BaseProvider,
    HistoricalData,
    QuoteData,
    StockInfo,
)

logger = logging.getLogger(__name__)

# Index/market symbols that should be skipped (not regular stocks)
INDEX_SYMBOLS = {"^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^OSPTSX", "^GSPTSE", "^FTSE", "^N100"}


def _is_index_symbol(symbol: str) -> bool:
    """Check if symbol is an index or market symbol, not a regular stock."""
    return symbol.startswith("^") or symbol in INDEX_SYMBOLS


class YahooFinanceProvider(BaseProvider):
    """Yahoo Finance provider using yfinance library.

    This is the primary provider as it has high limits and good data quality.
    Yahoo Finance does not enforce a hard daily request limit.  The real
    constraint is per-minute/per-hour rate limiting.  The daily_limit here
    is a safety valve against runaway loops, not a reflection of Yahoo's
    actual API limits.

    Includes retry logic with exponential backoff for transient failures.
    """

    name = "yahoo_finance"
    priority = 1
    daily_limit = 100_000
    minute_limit = 100
    supports_batch = True
    supported_exchanges: list[str] = []  # Empty = supports all exchanges (incl. SSE/SZSE/TSX)
    supports_realtime = True
    supports_historical = True

    # Retry configuration
    _max_retries = 3
    _retry_base_delay = 1.0  # seconds

    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Get current quote for a single symbol."""
        try:
            result = await asyncio.to_thread(self._fetch_quote, symbol)
            return result
        except Exception as e:
            logger.debug(f"Quote fetch exception for {symbol}: {e}")
            return None

    def _fetch_quote(self, symbol: str) -> QuoteData | None:
        """Synchronous quote fetch with retry logic (run in thread)."""
        if not YahooQuotaPool.can_request():
            logger.warning(
                "Yahoo daily quota exhausted",
                extra={
                    "operation": "realtime_fetch",
                    "provider": self.name,
                    "error_type": "rate_limit",
                },
            )
            return None
        YahooQuotaPool.record(1)

        last_error = None
        for attempt in range(self._max_retries):
            try:
                if attempt > 0:
                    time.sleep(self._retry_base_delay * (2**attempt))

                ticker = yf.Ticker(symbol)
                info = ticker.fast_info

                if not info:
                    return None

                # Safely extract price data - handle yfinance bugs gracefully
                last_price = self._safe_get(info, "lastPrice")
                if last_price is None:
                    return None

                # Get additional info for change calculation
                try:
                    prev_close = self._safe_get(info, "previousClose") or self._safe_get(
                        info, "regularMarketPreviousClose"
                    )

                    if prev_close and last_price and prev_close > 0:
                        change = Decimal(str(last_price)) - Decimal(str(prev_close))
                        change_percent = (change / Decimal(str(prev_close))) * 100
                    else:
                        change = None
                        change_percent = None
                except (TypeError, ZeroDivisionError, ValueError):
                    change = None
                    change_percent = None

                return QuoteData(
                    symbol=symbol,
                    price=Decimal(str(last_price)),
                    open_price=self._safe_decimal(info, "open"),
                    high=self._safe_decimal(info, "dayHigh"),
                    low=self._safe_decimal(info, "dayLow"),
                    close=self._safe_decimal(info, "previousClose"),
                    volume=self._safe_int(info, "lastVolume"),
                    change=change,
                    change_percent=change_percent,
                    timestamp=datetime.now(UTC),
                    provider=self.name,
                )

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                # Handle yfinance PriceHistory bug gracefully
                if "object has no attribute" in error_msg or "'pricehistory'" in error_msg:
                    logger.debug(f"yfinance PriceHistory bug for {symbol}, skipping")
                    return None
                if "delisted" in error_msg or "not found" in error_msg:
                    return None
                if attempt < self._max_retries - 1:
                    continue

        if last_error:
            logger.warning(
                "Quote fetch failed after retries",
                extra={
                    "operation": "realtime_fetch",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
        return None

    @staticmethod
    def _safe_get(info, key):
        """Safely get a value from ticker fast_info, handling yfinance bugs."""
        try:
            return info.get(key)
        except (AttributeError, TypeError):
            return None

    @staticmethod
    def _safe_decimal(info, key) -> Decimal | None:
        """Safely get a decimal value from ticker info."""
        try:
            val = info.get(key)
            if val is None:
                return None
            return Decimal(str(val))
        except (AttributeError, TypeError, ValueError, InvalidOperation):
            return None

    @staticmethod
    def _safe_int(info, key) -> int | None:
        """Safely get an integer value from ticker info."""
        try:
            val = info.get(key)
            if val is None:
                return None
            return int(val)
        except (AttributeError, TypeError, ValueError):
            return None

    async def get_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        """Get quotes for multiple symbols efficiently."""
        try:
            result = await asyncio.to_thread(self._fetch_quotes_batch, symbols)
            return result
        except Exception:
            logger.error(
                "Batch quote fetch failed",
                extra={
                    "operation": "batch_fetch",
                    "provider": self.name,
                    "error_type": "unknown_error",
                },
            )
            return []

    def _fetch_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        """Synchronous batch quote fetch with retry logic (run in thread)."""
        quotes = []

        # Filter out index symbols
        valid_symbols = [s for s in symbols if not _is_index_symbol(s)]
        if not valid_symbols:
            return []

        if not YahooQuotaPool.can_request(len(valid_symbols)):
            logger.warning(
                "Yahoo daily quota insufficient for batch",
                extra={
                    "operation": "batch_fetch",
                    "provider": self.name,
                    "error_type": "rate_limit",
                },
            )
            return []
        YahooQuotaPool.record(len(valid_symbols))

        # yfinance can handle space-separated symbols
        tickers = yf.Tickers(" ".join(valid_symbols))

        for symbol in valid_symbols:
            try:
                ticker = tickers.tickers.get(symbol)
                if ticker is None:
                    continue

                # Access fast_info with error handling for yfinance bugs
                try:
                    info = ticker.fast_info
                except AttributeError as e:
                    # Handle yfinance PriceHistory bug
                    if "PriceHistory" in str(e) or "_dividends" in str(e):
                        logger.debug(f"yfinance PriceHistory bug for {symbol} in batch, skipping")
                        continue
                    raise

                if not info:
                    continue

                # Safely extract price data
                last_price = YahooFinanceProvider._safe_get(info, "lastPrice")
                if last_price is None:
                    continue

                # Calculate change
                try:
                    prev_close = YahooFinanceProvider._safe_get(
                        info, "previousClose"
                    ) or YahooFinanceProvider._safe_get(info, "regularMarketPreviousClose")

                    if prev_close and last_price and prev_close > 0:
                        change = Decimal(str(last_price)) - Decimal(str(prev_close))
                        change_percent = (change / Decimal(str(prev_close))) * 100
                    else:
                        change = None
                        change_percent = None
                except (TypeError, ZeroDivisionError, ValueError):
                    change = None
                    change_percent = None

                quotes.append(
                    QuoteData(
                        symbol=symbol,
                        price=Decimal(str(last_price)),
                        open_price=YahooFinanceProvider._safe_decimal(info, "open"),
                        high=YahooFinanceProvider._safe_decimal(info, "dayHigh"),
                        low=YahooFinanceProvider._safe_decimal(info, "dayLow"),
                        close=YahooFinanceProvider._safe_decimal(info, "previousClose"),
                        volume=YahooFinanceProvider._safe_int(info, "lastVolume"),
                        change=change,
                        change_percent=change_percent,
                        timestamp=datetime.now(UTC),
                        provider=self.name,
                    )
                )
            except YFRateLimitError:
                # Yahoo is rate-limiting this IP.  Stop the batch here: every
                # further symbol would be one more rejected request, which
                # extends the ban and starves the other exchanges' quotes.
                # The next collection cycle picks up where this one stopped.
                logger.warning(
                    "Yahoo rate limit hit during batch — aborting the rest "
                    "of the batch to avoid extending the ban",
                    extra={
                        "operation": "batch_fetch",
                        "provider": self.name,
                        "error_type": "rate_limit",
                        "symbols_total": len(valid_symbols),
                        "symbols_done": len(quotes),
                    },
                )
                return quotes
            except Exception as e:
                # Handle yfinance bugs gracefully - don't log every failure
                error_msg = str(e).lower()
                if "object has no attribute" in error_msg or "'pricehistory'" in error_msg:
                    logger.debug(f"yfinance PriceHistory bug for {symbol} in batch")
                    continue
                logger.debug(f"Batch quote error for {symbol}: {e}")
                continue

        return quotes

    async def get_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        """Get historical daily prices for a symbol."""
        try:
            result = await asyncio.to_thread(self._fetch_historical, symbol, start_date, end_date)
            return result
        except Exception:
            logger.error(
                "Historical data fetch failed",
                extra={
                    "operation": "historical_fetch",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
            return []

    def _fetch_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        """Synchronous historical fetch with retry logic and error handling."""
        # Skip index symbols - they're not regular stocks
        if _is_index_symbol(symbol):
            logger.debug(f"Skipping index symbol: {symbol}")
            return []

        if not YahooQuotaPool.can_request():
            logger.warning(
                "Yahoo daily quota exhausted",
                extra={
                    "operation": "historical_fetch",
                    "provider": self.name,
                    "error_type": "rate_limit",
                },
            )
            return []
        YahooQuotaPool.record(1)

        last_error = None
        for attempt in range(self._max_retries):
            try:
                ticker = yf.Ticker(symbol)
                # Add retry delay for rate limiting
                if attempt > 0:
                    time.sleep(self._retry_base_delay * (2**attempt))

                df = ticker.history(start=start_date, end=end_date, interval="1d")

                if df.empty:
                    # Empty result is valid - symbol may have no trading data in range
                    return []

                historical = []
                for idx, row in df.iterrows():
                    historical.append(
                        HistoricalData(
                            symbol=symbol,
                            date=idx.date(),
                            open_price=Decimal(str(row["Open"])) if row["Open"] else None,
                            high=Decimal(str(row["High"])) if row["High"] else None,
                            low=Decimal(str(row["Low"])) if row["Low"] else None,
                            close=Decimal(str(row["Close"])) if row["Close"] else None,
                            adj_close=Decimal(str(row["Close"]))
                            if row["Close"]
                            else None,  # yfinance adjusts by default
                            adjustment=ADJUSTMENT_SPLIT_DIVIDEND,
                            volume=int(row["Volume"]) if row["Volume"] else None,
                            provider=self.name,
                        )
                    )

                return historical

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                # Don't retry for certain permanent errors
                if "delisted" in error_msg or "not found" in error_msg:
                    logger.debug(f"Permanent error for {symbol}: {e}")
                    return []
                # Retry for transient errors
                if attempt < self._max_retries - 1:
                    self._retry_base_delay * (2**attempt)
                    logger.warning(
                        "Transient error during historical fetch, retrying",
                        extra={
                            "operation": "historical_fetch",
                            "provider": self.name,
                            "symbol": symbol,
                            "error_type": "connection_error",
                        },
                    )
                    continue

        # All retries exhausted
        if last_error:
            logger.warning(
                "Historical fetch failed after retries",
                extra={
                    "operation": "historical_fetch",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
        return []

    async def get_stock_info(self, symbol: str) -> StockInfo | None:
        """Get stock information."""
        try:
            result = await asyncio.to_thread(self._fetch_stock_info, symbol)
            return result
        except Exception:
            logger.error(
                "Stock info fetch failed",
                extra={
                    "operation": "stock_info",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
            return None

    def _fetch_stock_info(self, symbol: str) -> StockInfo | None:
        """Synchronous stock info fetch (run in thread)."""
        ticker = yf.Ticker(symbol)
        info = ticker.info

        if not info or "shortName" not in info:
            return None

        return StockInfo(
            symbol=symbol,
            name=info.get("shortName") or info.get("longName") or symbol,
            exchange=info.get("exchange"),
            sector=(info.get("sector") or "").strip() or None,
            industry=(info.get("industry") or "").strip() or None,
            market_cap=info.get("marketCap"),
        )

    async def search_stocks(self, query: str) -> list[StockInfo]:
        """Search for stocks - yfinance doesn't have great search, return empty."""
        # yfinance doesn't have a good search API, so we return empty
        # In practice, we'll pre-populate our database with S&P 500
        return []
