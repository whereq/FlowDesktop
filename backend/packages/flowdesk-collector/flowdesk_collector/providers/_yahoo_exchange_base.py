"""Base class for Yahoo Finance-backed exchange providers.

Eliminates duplication across JPX (.T), SGX (.SI), TAI (.TW), and KSC (.KS)
providers.  Each subclass only needs to set a few class attributes:

    class JPExchangeProvider(YahooExchangeProvider):
        name = "jp_exchange"
        supported_exchanges = ["JPX"]
        _suffix = ".T"
        _exchange_label = "JPX"

The base class handles all Yahoo Finance interactions: single quotes,
batch quotes, historical OHLCV, stock info, retry logic, and rate limiting.

Shared Yahoo Quota Pool
-----------------------
Yahoo Finance does not enforce a hard daily request limit.  The real
constraint is a per-minute/per-hour rate limit (~2000 req/hour).  The
daily quota pool exists as a safety valve to prevent runaway loops from
making unbounded requests, but the limit is set high enough (100 000)
to cover our full symbol universe (~15 000 stocks across all exchanges)
with room for multiple collection cycles per day.
"""

import asyncio
import logging
from datetime import UTC, date
from decimal import Decimal
from typing import ClassVar

import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from flowdesk_collector.providers._utils import (
    safe_decimal,
    safe_decimal_from_info,
    safe_get,
    safe_int,
    safe_int_from_info,
    utcnow,
)
from flowdesk_collector.providers.base import (
    ADJUSTMENT_SPLIT_DIVIDEND,
    BaseProvider,
    HistoricalData,
    QuoteData,
    StockInfo,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared Yahoo Finance quota pool
# ---------------------------------------------------------------------------


class YahooQuotaPool:
    """Global request counter shared across all Yahoo Finance-backed providers.

    Yahoo Finance does not enforce a hard daily request limit.  The real
    constraint is per-minute/per-hour rate limiting (~2000 req/hour).  This
    pool acts as a safety valve against runaway loops; the daily cap is set
    high enough to cover the full symbol universe across multiple collection
    cycles.  The counter resets at midnight UTC.
    """

    _daily_limit: ClassVar[int] = 100_000
    _requests_today: ClassVar[int] = 0
    _last_reset_day: ClassVar[int | None] = None  # day-of-year

    @classmethod
    def can_request(cls, count: int = 1) -> bool:
        """Return True if *count* requests can be made within the daily budget."""
        cls._maybe_reset()
        return cls._requests_today + count <= cls._daily_limit

    @classmethod
    def record(cls, count: int = 1) -> None:
        """Record that *count* requests were made."""
        cls._maybe_reset()
        cls._requests_today += count

    @classmethod
    def remaining(cls) -> int:
        cls._maybe_reset()
        return max(0, cls._daily_limit - cls._requests_today)

    @classmethod
    def _maybe_reset(cls) -> None:
        """Reset counter if the UTC day has changed."""
        from datetime import datetime

        today = datetime.now(UTC).timetuple().tm_yday
        if cls._last_reset_day != today:
            cls._requests_today = 0
            cls._last_reset_day = today


class YahooExchangeProvider(BaseProvider):
    """Abstract base for exchange providers that use Yahoo Finance as their backend.

    Subclasses MUST set:
        name               — provider identifier (e.g. "jp_exchange")
        supported_exchanges — list with one canonical exchange code
        _suffix            — Yahoo Finance symbol suffix (e.g. ".T")
        _exchange_label    — exchange code used in StockInfo (e.g. "JPX")

    Optional overrides:
        priority, daily_limit, minute_limit, _max_retries, _retry_base_delay
    """

    # --- Subclass MUST override these ---
    name: str = ""
    supported_exchanges: list[str] = []
    _suffix: str = ""
    _exchange_label: str = ""

    # --- Defaults (subclass MAY override) ---
    priority = 2
    daily_limit = 100_000
    minute_limit = 100
    supports_batch = True
    supports_realtime = True
    supports_historical = True

    _max_retries = 3
    _retry_base_delay = 1.0  # seconds

    # ------------------------------------------------------------------
    # Symbol helpers
    # ------------------------------------------------------------------

    def _from_yahoo(self, symbol: str) -> str | None:
        """Strip the exchange suffix to get the bare stock code."""
        if symbol.endswith(self._suffix):
            return symbol[: -len(self._suffix)]
        return None

    def _to_yahoo(self, code: str) -> str:
        """Append the exchange suffix to a bare stock code."""
        return f"{code}{self._suffix}"

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    async def get_quote(self, symbol: str) -> QuoteData | None:
        code = self._from_yahoo(symbol)
        if code is None:
            return None

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

        try:
            yahoo_sym = self._to_yahoo(code)
            YahooQuotaPool.record(1)
            ticker = yf.Ticker(yahoo_sym)
            info = await asyncio.to_thread(lambda: ticker.fast_info)

            if not info:
                return None

            last_price = safe_get(info, "lastPrice")
            if last_price is None:
                return None

            change, change_percent = self._calc_change(info, last_price)

            return QuoteData(
                symbol=symbol,
                price=Decimal(str(last_price)),
                open_price=safe_decimal_from_info(info, "open"),
                high=safe_decimal_from_info(info, "dayHigh"),
                low=safe_decimal_from_info(info, "dayLow"),
                close=safe_decimal_from_info(info, "previousClose"),
                volume=safe_int_from_info(info, "lastVolume"),
                change=change,
                change_percent=change_percent,
                timestamp=utcnow(),
                provider=self.name,
            )
        except Exception as exc:
            logger.debug(f"{self._exchange_label} quote fetch failed for {symbol}: {exc}")
            return None

    async def get_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        if not symbols:
            return []

        if not YahooQuotaPool.can_request(len(symbols)):
            logger.warning(
                "Yahoo daily quota insufficient for batch",
                extra={
                    "operation": "batch_fetch",
                    "provider": self.name,
                    "error_type": "rate_limit",
                },
            )
            return []

        yahoo_symbols: list[str] = []
        symbol_map: dict[str, str] = {}  # yahoo → original
        for sym in symbols:
            code = self._from_yahoo(sym)
            if code:
                yahoo_sym = self._to_yahoo(code)
                yahoo_symbols.append(yahoo_sym)
                symbol_map[yahoo_sym] = sym

        if not yahoo_symbols:
            return []

        try:
            YahooQuotaPool.record(len(yahoo_symbols))
            tickers = yf.Tickers(" ".join(yahoo_symbols))
            results: list[QuoteData] = []

            for yahoo_sym in yahoo_symbols:
                ticker = tickers.tickers.get(yahoo_sym)
                if ticker is None:
                    continue

                try:
                    info = ticker.fast_info
                except YFRateLimitError:
                    # Yahoo is rate-limiting this IP.  Stop the batch here:
                    # every further symbol would be one more rejected request,
                    # which extends the ban and starves the other exchanges'
                    # quotes.  The next cycle picks up where this one stopped.
                    logger.warning(
                        f"{self._exchange_label} Yahoo rate limit hit during "
                        "batch — aborting the rest of the batch to avoid "
                        "extending the ban",
                        extra={
                            "operation": "batch_fetch",
                            "provider": self.name,
                            "error_type": "rate_limit",
                            "symbols_total": len(yahoo_symbols),
                            "symbols_done": len(results),
                        },
                    )
                    return results
                except AttributeError as exc:
                    if "PriceHistory" in str(exc) or "_dividends" in str(exc):
                        logger.debug(f"yfinance PriceHistory bug for {yahoo_sym}")
                        continue
                    raise

                if not info:
                    continue

                last_price = safe_get(info, "lastPrice")
                if last_price is None:
                    continue

                original_sym = symbol_map.get(yahoo_sym, yahoo_sym)
                change, change_percent = self._calc_change(info, last_price)

                results.append(
                    QuoteData(
                        symbol=original_sym,
                        price=Decimal(str(last_price)),
                        open_price=safe_decimal_from_info(info, "open"),
                        high=safe_decimal_from_info(info, "dayHigh"),
                        low=safe_decimal_from_info(info, "dayLow"),
                        close=safe_decimal_from_info(info, "previousClose"),
                        volume=safe_int_from_info(info, "lastVolume"),
                        change=change,
                        change_percent=change_percent,
                        timestamp=utcnow(),
                        provider=self.name,
                    )
                )

            return results

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

    async def get_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        code = self._from_yahoo(symbol)
        if code is None:
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

        yahoo_sym = self._to_yahoo(code)

        for attempt in range(self._max_retries):
            try:
                if attempt > 0:
                    await asyncio.sleep(self._retry_base_delay * (2**attempt))

                YahooQuotaPool.record(1)
                ticker = yf.Ticker(yahoo_sym)
                df = await asyncio.to_thread(
                    ticker.history,
                    start=start_date,
                    end=end_date,
                    interval="1d",
                )

                if df is None or df.empty:
                    return []

                results: list[HistoricalData] = []
                for idx, row in df.iterrows():
                    close = safe_decimal(row.get("Close"))
                    if close is None:
                        continue
                    results.append(
                        HistoricalData(
                            symbol=symbol,
                            date=idx.date(),
                            open_price=safe_decimal(row.get("Open")),
                            high=safe_decimal(row.get("High")),
                            low=safe_decimal(row.get("Low")),
                            close=close,
                            adj_close=close,
                            adjustment=ADJUSTMENT_SPLIT_DIVIDEND,
                            volume=safe_int(row.get("Volume")),
                            provider=self.name,
                        )
                    )
                return sorted(results, key=lambda x: x.date)

            except Exception as exc:
                if "delisted" in str(exc).lower() or "not found" in str(exc).lower():
                    return []
                if attempt < self._max_retries - 1:
                    continue

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
        code = self._from_yahoo(symbol)
        if code is None:
            return None

        if not YahooQuotaPool.can_request():
            return None

        yahoo_sym = self._to_yahoo(code)

        try:
            YahooQuotaPool.record(1)
            ticker = yf.Ticker(yahoo_sym)
            info = await asyncio.to_thread(lambda: ticker.info)

            if not info or "shortName" not in info:
                return None

            return StockInfo(
                symbol=symbol,
                name=info.get("shortName") or info.get("longName") or symbol,
                exchange=self._exchange_label,
                sector=(info.get("sector") or "").strip() or None,
                industry=(info.get("industry") or "").strip() or None,
                market_cap=info.get("marketCap"),
            )
        except Exception as exc:
            logger.debug(f"{self._exchange_label} stock info fetch failed for {symbol}: {exc}")
            return None

    async def search_stocks(self, query: str) -> list[StockInfo]:
        # Yahoo Finance doesn't provide search; universe is pre-populated
        return []

    async def is_available(self) -> bool:
        try:
            import yfinance  # noqa: F401

            return True
        except ImportError:
            logger.warning("yfinance package not installed.")
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_change(info, last_price) -> tuple[Decimal | None, Decimal | None]:
        """Calculate price change and change percent from fast_info."""
        try:
            prev_close = safe_get(info, "previousClose") or safe_get(
                info, "regularMarketPreviousClose"
            )
            if prev_close and last_price and prev_close > 0:
                change = Decimal(str(last_price)) - Decimal(str(prev_close))
                change_percent = (change / Decimal(str(prev_close))) * 100
                return change, change_percent
        except (TypeError, ZeroDivisionError, ValueError):
            pass
        return None, None
