"""AKShare provider for Chinese A-share market data.

AKShare aggregates data from East Money, Sina Finance, and other Chinese
financial platforms.  It is free, requires no API key, and is the primary
source of truth for Chinese stock names and quotes in this system.

Symbol format conversions
-------------------------
Yahoo Finance  ←→  AKShare bare code
  600519.SS   ←→   600519   (SSE: Shanghai, codes start with 6)
  000858.SZ   ←→   000858   (SZSE: Shenzhen, codes start with 0/2/3)

Exchange detection from bare code
----------------------------------
  Starts with 6          → SSE
  Starts with 0, 2, or 3 → SZSE
"""

import asyncio
import logging
import time
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from flowdesk_collector.eastmoney_gate import (
    EastMoneyCoolingDown,
    EastMoneyGate,
    eastmoney_allowed,
)
from flowdesk_collector.providers.base import (
    ADJUSTMENT_SPLIT_DIVIDEND,
    BaseProvider,
    ChineseNameProvider,
    ChineseStockNameData,
    HistoricalData,
    QuoteData,
    StockInfo,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Symbol conversion helpers
# ---------------------------------------------------------------------------


def _normalize_cn_name(name: str) -> str:
    """Normalize a Chinese stock name from AKShare.

    AKShare pads short names with spaces and uses full-width ASCII letters
    (e.g. "万  科Ａ" instead of "万科A").  This function:
      1. Applies NFKC normalization (full-width → half-width: Ａ → A)
      2. Collapses all internal whitespace runs to a single space
      3. Strips leading/trailing whitespace
    """
    name = unicodedata.normalize("NFKC", name)
    return " ".join(name.split())


def _exchange_from_code(code: str) -> str | None:
    """Determine exchange from bare 6-digit stock code.

    Returns None for codes that don't belong to SSE or SZSE (e.g. Beijing
    Stock Exchange codes starting with 4 or 8).
    """
    if code.startswith("6"):
        return "SSE"
    if code[0] in ("0", "2", "3"):
        return "SZSE"
    # Codes starting with 4/8 are Beijing Stock Exchange (BSE),
    # 9 = SSE B-shares — not supported by stock_zh_a_spot_em()
    return None


def _to_yahoo_symbol(code: str) -> str | None:
    """Convert bare AKShare code to Yahoo Finance format.

    Returns None for codes that don't map to SSE or SZSE.
    """
    exchange = _exchange_from_code(code)
    if exchange is None:
        return None
    suffix = ".SS" if exchange == "SSE" else ".SZ"
    return code + suffix


def _to_akshare_code(yahoo_symbol: str) -> str | None:
    """Strip Yahoo Finance suffix to get bare AKShare code.

    Returns None for non-Chinese symbols.
    """
    if yahoo_symbol.endswith(".SS") or yahoo_symbol.endswith(".SZ"):
        return yahoo_symbol.rsplit(".", 1)[0]
    return None


def _safe_decimal(value) -> Decimal | None:
    """Convert a pandas/numpy value to Decimal, returning None on failure."""
    try:
        import pandas as pd

        if pd.isna(value):
            return None
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    """Convert a pandas/numpy value to int, returning None on failure."""
    try:
        import pandas as pd

        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class AKShareProvider(BaseProvider, ChineseNameProvider):
    """AKShare data provider — Chinese A-share stocks only.

    Capabilities
    ------------
    - Real-time quotes for all SSE / SZSE listed stocks (East Money feed).
    - Full historical OHLCV with forward-adjusted close (前复权).
    - Bulk Chinese stock name registry (source of truth).

    Rate limiting
    -------------
    AKShare has no official rate limit but scrapes live websites.
    A self-imposed ``minute_limit`` of 30 requests/min and a small
    inter-request delay protect against throttling.

    Caching
    -------
    ``stock_zh_a_spot_em()`` fetches *all* ~5 500 A-share stocks in one
    network call, so the result is cached for ``_SPOT_CACHE_TTL`` seconds.
    Individual ``get_quote()`` and ``get_quotes_batch()`` calls share this
    cache, making batch operations very efficient.
    """

    name = "akshare"
    priority = 2  # Higher than Yahoo (0) is not correct - see note below
    daily_limit = None  # No hard daily cap
    minute_limit = 30  # Self-imposed politeness limit
    supports_batch = True  # Batch is native — one call returns all stocks
    supported_exchanges = ["SSE", "SZSE"]
    supports_realtime = True
    supports_historical = True

    # NOTE on priority: AKShare uses priority=2 so the orchestrator's explicit
    # _CHINA_PREFERRED_PROVIDERS routing (not the generic priority ordering)
    # ensures AKShare is tried before Yahoo for Chinese stocks.

    # Class-level spot data cache shared across all instances
    _spot_cache: ClassVar[tuple[object, float, float] | None] = None  # (DataFrame, timestamp, ttl)
    _SPOT_CACHE_TTL: ClassVar[float] = 60.0  # seconds (East Money — fast single fetch)
    _SPOT_CACHE_TTL_SINA: ClassVar[float] = 300.0  # Sina bulk fetch takes ~85s — cache longer
    _consecutive_failures: ClassVar[int] = 0
    _CIRCUIT_BREAKER_THRESHOLD: ClassVar[int] = 5  # Switch to backup after 5 consecutive failures
    _circuit_breaker_reset_seconds: ClassVar[float] = 300.0  # Reset after 5 minutes cooldown
    _last_failure_time: ClassVar[float] = 0.0  # Timestamp of last failure

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _fetch_spot_eastmoney():
        """Fetch the full A-share spot table from East Money (primary source).

        East Money bans the collector's overseas IP for tens of minutes at a
        time and every call during the ban extends it, so the shared
        :mod:`collector.eastmoney_gate` keeps every caller out until the ban
        expires instead of each one retrying on its own schedule.
        """
        if not eastmoney_allowed():
            raise EastMoneyCoolingDown(
                "East Money is cooling down after an upstream rate-limit "
                f"({int(EastMoneyGate.cooldown_remaining() // 60)} min left)"
            )

        import akshare as ak

        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as exc:
            EastMoneyGate.record_failure(exc)
            raise
        EastMoneyGate.record_success()
        return df

    @staticmethod
    def _fetch_spot_sina():
        """Fetch the full A-share spot table from Sina (fallback source).

        East Money's push2 API blocks some overseas IPs (connection reset);
        Sina remains reachable.  The Sina table is normalized to the East
        Money schema expected by ``_row_to_quote`` and
        ``classify_missing_symbols``:
        - 代码 carries an exchange prefix (``sh600519``) — stripped to bare code
        - 成交量 is in shares, not lots (手) — divided by 100
        """
        import contextlib
        import io

        import akshare as ak

        # stock_zh_a_spot paginates ~70 requests with a tqdm progress bar
        # that would flood the container logs — silence it.  The long
        # pagination is vulnerable to transient DNS failures, so retry once.
        last_exc: Exception | None = None
        for _attempt in range(2):
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    df = ak.stock_zh_a_spot()
                break
            except Exception as exc:
                last_exc = exc
        else:
            raise last_exc
        df = df.copy()
        df["代码"] = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
        df["成交量"] = df["成交量"] / 100
        return df

    async def _get_spot_data(self):
        """Return cached real-time spot data, refreshing if stale.

        Tries East Money first, then Sina as fallback.  Implements circuit
        breaker pattern - after consecutive failures, returns stale cache or
        None to prevent wasting time on failing provider.
        Circuit breaker auto-resets after _circuit_breaker_reset_seconds.
        """
        now = time.monotonic()

        # Check if circuit breaker should auto-reset after cooldown period
        if (
            AKShareProvider._consecutive_failures >= AKShareProvider._CIRCUIT_BREAKER_THRESHOLD
            and AKShareProvider._last_failure_time > 0
        ):
            elapsed = now - AKShareProvider._last_failure_time
            if elapsed >= AKShareProvider._circuit_breaker_reset_seconds:
                logger.info(
                    f"AKShare circuit breaker auto-resetting after {elapsed:.0f}s cooldown. "
                    f"Previous failures: {AKShareProvider._consecutive_failures}"
                )
                AKShareProvider._consecutive_failures = 0
                AKShareProvider._last_failure_time = 0.0
            else:
                # Still in cooldown period
                if AKShareProvider._spot_cache is not None:
                    logger.warning(
                        "Circuit breaker active, using stale cache",
                        extra={
                            "operation": "realtime_fetch",
                            "provider": self.name,
                            "error_type": "rate_limit",
                        },
                    )
                    return AKShareProvider._spot_cache[0]
                else:
                    AKShareProvider._circuit_breaker_reset_seconds - elapsed
                    logger.error(
                        "Circuit breaker open, no cache available",
                        extra={
                            "operation": "realtime_fetch",
                            "provider": self.name,
                            "error_type": "connection_error",
                        },
                    )
                    return None

        cached = AKShareProvider._spot_cache
        if cached is not None and (now - cached[1]) < cached[2]:
            # Reset failure counter on successful cache hit
            if AKShareProvider._consecutive_failures > 0:
                AKShareProvider._consecutive_failures = 0
            return cached[0]

        for fetch, source, ttl in (
            (self._fetch_spot_eastmoney, "eastmoney", self._SPOT_CACHE_TTL),
            (self._fetch_spot_sina, "sina", self._SPOT_CACHE_TTL_SINA),
        ):
            try:
                df = await asyncio.to_thread(fetch)
                if df is None or df.empty:
                    raise ValueError("Empty DataFrame returned")

                AKShareProvider._spot_cache = (df, time.monotonic(), ttl)
                # Reset failure counter on successful fetch
                if AKShareProvider._consecutive_failures > 0:
                    logger.info(
                        f"AKShare recovered after {AKShareProvider._consecutive_failures} failures"
                    )
                    AKShareProvider._consecutive_failures = 0
                if source != "eastmoney":
                    logger.info(f"AKShare spot data fetched via {source} fallback ({len(df)} rows)")
                return df
            except EastMoneyCoolingDown:
                # Expected during an upstream ban — no request was made, so
                # there is nothing to warn about.  Fall through to Sina.
                logger.debug(
                    "East Money is cooling down; using the Sina A-share spot feed",
                    extra={
                        "operation": "realtime_fetch",
                        "provider": self.name,
                        "source": source,
                        "error_type": "rate_limit",
                    },
                )
                continue
            except Exception:
                logger.warning(
                    "Spot data fetch failed",
                    extra={
                        "operation": "realtime_fetch",
                        "provider": self.name,
                        "source": source,
                        "error_type": "connection_error",
                    },
                )
                continue

        # All spot sources failed
        AKShareProvider._consecutive_failures += 1
        AKShareProvider._last_failure_time = time.monotonic()
        # Return stale cache if available
        if AKShareProvider._spot_cache is not None:
            logger.warning("AKShare: returning stale spot cache after fetch error")
            return AKShareProvider._spot_cache[0]
        return None

    def _row_to_quote(self, row, symbol: str) -> QuoteData | None:
        """Convert a spot DataFrame row to QuoteData."""
        price = _safe_decimal(row.get("最新价"))
        if price is None or price == 0:
            return None

        # AKShare returns volume in 手 (lots, 1 lot = 100 shares)
        raw_vol = _safe_int(row.get("成交量"))
        volume = raw_vol * 100 if raw_vol is not None else None

        return QuoteData(
            symbol=symbol,
            price=price,
            open_price=_safe_decimal(row.get("今开")),
            high=_safe_decimal(row.get("最高")),
            low=_safe_decimal(row.get("最低")),
            close=_safe_decimal(row.get("昨收")),
            volume=volume,
            change=_safe_decimal(row.get("涨跌额")),
            change_percent=_safe_decimal(row.get("涨跌幅")),
            timestamp=datetime.now(UTC),
            provider=self.name,
        )

    # ---------------------------------------------------------------------------
    # BaseProvider interface
    # ---------------------------------------------------------------------------

    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Get real-time quote for a single Chinese stock."""
        code = _to_akshare_code(symbol)
        if code is None:
            return None

        df = await self._get_spot_data()
        if df is None or df.empty:
            return None

        rows = df[df["代码"] == code]
        if rows.empty:
            return None

        return self._row_to_quote(rows.iloc[0].to_dict(), symbol)

    async def get_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        """Get real-time quotes for multiple Chinese stocks in a single fetch."""
        if not symbols:
            return []

        df = await self._get_spot_data()
        if df is None or df.empty:
            return []

        # Build code → yahoo_symbol mapping for fast lookup
        code_to_symbol: dict[str, str] = {}
        for sym in symbols:
            code = _to_akshare_code(sym)
            if code:
                code_to_symbol[code] = sym

        if not code_to_symbol:
            return []

        subset = df[df["代码"].isin(code_to_symbol.keys())]
        results: list[QuoteData] = []
        for _, row in subset.iterrows():
            code = row["代码"]
            yahoo_sym = code_to_symbol.get(code)
            if yahoo_sym is None:
                continue
            quote = self._row_to_quote(row.to_dict(), yahoo_sym)
            if quote:
                results.append(quote)

        return results

    async def classify_missing_symbols(self, symbols: list[str]) -> tuple[set[str], set[str]]:
        """Classify symbols that got no quote into *suspended* vs *not in feed*.

        Returns
        -------
        (suspended, not_in_feed)
            suspended   — row exists in East Money feed but price is 0/NaN (停牌)
            not_in_feed — bare code not present in the feed at all (delisted
                          or not an A-share stock)
        """
        suspended: set[str] = set()
        not_in_feed: set[str] = set()

        if not symbols:
            return suspended, not_in_feed

        df = await self._get_spot_data()
        if df is None or df.empty:
            return suspended, not_in_feed

        code_to_symbol: dict[str, str] = {}
        for sym in symbols:
            code = _to_akshare_code(sym)
            if code:
                code_to_symbol[code] = sym

        if not code_to_symbol:
            return suspended, not_in_feed

        import pandas as pd

        feed_codes = set(df["代码"].tolist())

        for code, yahoo_sym in code_to_symbol.items():
            if code not in feed_codes:
                not_in_feed.add(yahoo_sym)
                continue
            # Code is in the feed — check if suspended (price=0/NaN)
            rows = df[df["代码"] == code]
            if not rows.empty:
                price = rows.iloc[0].get("最新价")
                if pd.isna(price) or float(price) == 0:
                    suspended.add(yahoo_sym)

        return suspended, not_in_feed

    async def get_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        """Fetch daily OHLCV history for a Chinese stock (forward-adjusted)."""
        code = _to_akshare_code(symbol)
        if code is None:
            return []

        # Eastmoney's push2his endpoint (stock_zh_a_hist) drops connections from
        # this host's overseas egress (RemoteDisconnected), so fetch history from
        # the Sina-backed daily endpoint, which is reachable and forward-adjustable.
        # Sina wants an exchange prefix (sh/sz) on the bare code.
        sina_symbol = ("sh" if symbol.endswith(".SS") else "sz") + code
        try:
            import akshare as ak

            df = await asyncio.to_thread(
                ak.stock_zh_a_daily,
                symbol=sina_symbol,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",  # 前复权 — forward-adjusted
            )
        except Exception as exc:
            logger.error(
                "Historical fetch failed",
                extra={
                    "operation": "historical_fetch",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "connection_error",
                    "error": str(exc)[:200],
                },
            )
            return []

        if df is None or df.empty:
            return []

        import pandas as pd

        results: list[HistoricalData] = []
        for _, row in df.iterrows():
            try:
                raw_date = row.get("date")
                if pd.isna(raw_date):
                    continue
                record_date = (
                    raw_date.date()
                    if hasattr(raw_date, "date")
                    else datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
                )

                close = _safe_decimal(row.get("close"))
                if close is None:
                    continue

                # Sina's `volume` is already in shares (unlike Eastmoney's 手).
                volume = _safe_int(row.get("volume"))

                results.append(
                    HistoricalData(
                        symbol=symbol,
                        date=record_date,
                        open_price=_safe_decimal(row.get("open")),
                        high=_safe_decimal(row.get("high")),
                        low=_safe_decimal(row.get("low")),
                        close=close,
                        adj_close=close,  # already forward-adjusted
                        adjustment=ADJUSTMENT_SPLIT_DIVIDEND,
                        volume=volume,
                        provider=self.name,
                    )
                )
            except Exception as exc:
                logger.debug(f"AKShare history row parse error for {symbol}: {exc}")
                continue

        return sorted(results, key=lambda x: x.date)

    async def get_stock_info(self, symbol: str) -> StockInfo | None:
        """Get stock metadata.  Name is sourced from the Chinese name registry."""
        code = _to_akshare_code(symbol)
        if code is None:
            return None

        df = await self._get_spot_data()
        if df is None or df.empty:
            return None

        rows = df[df["代码"] == code]
        if rows.empty:
            return None

        row = rows.iloc[0]
        name_cn = _normalize_cn_name(str(row.get("名称", symbol)))
        exchange = _exchange_from_code(code) or "SZSE"

        # 总市值 is in CNY yuan — convert to int if present
        raw_cap = row.get("总市值")
        market_cap: int | None = None
        try:
            if raw_cap is not None:
                market_cap = int(float(raw_cap))
        except (ValueError, TypeError):
            pass

        return StockInfo(
            symbol=symbol,
            name=name_cn,
            exchange=exchange,
            market_cap=market_cap,
        )

    async def search_stocks(self, query: str) -> list[StockInfo]:
        """Search Chinese stocks by code or name."""
        df = await self._get_spot_data()
        if df is None or df.empty:
            return []

        query.upper()
        try:
            mask = df["代码"].str.contains(query, case=False, na=False) | df["名称"].str.contains(
                query, case=False, na=False
            )
            matches = df[mask].head(20)
        except Exception:
            return []

        results: list[StockInfo] = []
        for _, row in matches.iterrows():
            code = str(row["代码"])
            yahoo_sym = _to_yahoo_symbol(code)
            exchange = _exchange_from_code(code)
            if yahoo_sym is None or exchange is None:
                continue
            results.append(
                StockInfo(
                    symbol=yahoo_sym,
                    name=str(row.get("名称", code)),
                    exchange=exchange,
                )
            )
        return results

    async def is_available(self) -> bool:
        """AKShare is always available — no API key required."""
        try:
            import akshare  # noqa: F401

            return True
        except ImportError:
            logger.warning("AKShare package not installed. Run: pip install akshare")
            return False

    # ---------------------------------------------------------------------------
    # ChineseNameProvider interface
    # ---------------------------------------------------------------------------

    async def get_all_chinese_names(self) -> list[ChineseStockNameData]:
        """Fetch the full A-share name registry from AKShare.

        Uses ``stock_info_a_code_name()`` which returns a lightweight
        code→name table (~5 500 rows) without price data.  This is the
        most reliable bulk source for Chinese stock names.
        """
        try:
            import akshare as ak

            df = await asyncio.to_thread(ak.stock_info_a_code_name)
        except Exception:
            logger.error(
                "Chinese name registry fetch failed",
                extra={
                    "operation": "stock_info",
                    "provider": self.name,
                    "error_type": "unknown_error",
                },
            )
            return []

        if df is None or df.empty:
            return []

        results: list[ChineseStockNameData] = []
        for _, row in df.iterrows():
            try:
                code = str(row.get("code", "")).strip().zfill(6)
                name_cn = _normalize_cn_name(str(row.get("name", "")))
                if not code or not name_cn or len(code) != 6:
                    continue
                exchange = _exchange_from_code(code)
                yahoo_sym = _to_yahoo_symbol(code)
                if exchange is None or yahoo_sym is None:
                    continue
                results.append(
                    ChineseStockNameData(
                        symbol=yahoo_sym,
                        code=code,
                        name_cn=name_cn,
                        exchange=exchange,
                        provider=self.name,
                    )
                )
            except Exception as exc:
                logger.debug(f"AKShare name row parse error: {exc}")
                continue

        logger.info(f"AKShare: fetched {len(results)} Chinese stock names")
        return results
