"""Abstract base class for data providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

# ---------------------------------------------------------------------------
# Adjustment vocabulary for historical prices
# ---------------------------------------------------------------------------
#
# Providers disagree about what a "close" means: some return the raw traded
# price, some back out splits, some also adjust for dividends.  A consumer
# that stitches two providers' series together gets a chart with a fake jump
# in it.  Every historical row therefore records which of these applies.
#
#   ADJUSTMENT_SPLIT          — adjusted for stock splits only
#   ADJUSTMENT_SPLIT_DIVIDEND — adjusted for splits and dividends
#   ADJUSTMENT_NONE           — raw, as-traded prices
#   ADJUSTMENT_UNKNOWN        — the provider does not state its convention
#
# Per-provider basis (verified against each API's documentation):
#
#   yahoo / hk_exchange / _yahoo_exchange_base
#       yfinance's history() defaults to auto_adjust=True, which adjusts for
#       splits AND dividends (forward-adjusted).
#   akshare        adjust="qfq" (前复权) — forward-adjusted for splits+dividends.
#   polygon        ?adjusted=true — split-adjusted.
#   twelvedata     the `adjust` parameter defaults to "splits".
#   tiingo / fmp / alphavantage
#       their adjClose / "5. adjusted close" fields are split+dividend adjusted.
#   alpaca         the `adjustment` parameter defaults to "raw".
#   finnhub        /stock/candle returns raw closes.
#   stooq          raw CSV quotes.
#   tushare        pro_bar is called without an `adj` factor — raw.
#   jp_exchange_jquants
#       /equities/bars/daily returns raw OHLC (adjClose is a separate field).
ADJUSTMENT_SPLIT = "split_adjusted"
ADJUSTMENT_SPLIT_DIVIDEND = "split_dividend_adjusted"
ADJUSTMENT_NONE = "unadjusted"
ADJUSTMENT_UNKNOWN = "unknown"

#: Every value the ``adjustment`` column may hold.
ADJUSTMENT_VALUES = (
    ADJUSTMENT_SPLIT,
    ADJUSTMENT_SPLIT_DIVIDEND,
    ADJUSTMENT_NONE,
    ADJUSTMENT_UNKNOWN,
)


class ProviderRateLimitedError(Exception):
    """Raised by a provider when the API returns a daily quota / rate-limit error.

    The orchestrator catches this to:
    1. Increment the provider's daily_used counter (so the DB reflects reality).
    2. Mark the provider is_available=False for the rest of the day so it is
       not retried on every subsequent symbol.
    """


@dataclass
class QuoteData:
    """Normalized quote data from any provider."""

    symbol: str
    price: Decimal
    open_price: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    change: Decimal | None = None
    change_percent: Decimal | None = None
    timestamp: datetime = None
    provider: str = ""

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        elif self.timestamp.tzinfo is not None:
            # DB columns are TIMESTAMP WITHOUT TIME ZONE — strip tzinfo
            self.timestamp = self.timestamp.replace(tzinfo=None)


@dataclass
class HistoricalData:
    """Normalized historical price data from any provider.

    ``adjustment`` records what the provider actually did to the prices, so
    a consumer can tell an adjusted close from a raw one.  See the
    ``ADJUSTMENT_*`` constants below for the vocabulary.
    """

    symbol: str
    date: date
    open_price: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    adj_close: Decimal | None = None
    volume: int | None = None
    provider: str = ""
    adjustment: str = ""


@dataclass
class StockInfo:
    """Normalized stock information from any provider."""

    symbol: str
    name: str
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None


@dataclass
class FundamentalData:
    """Fundamental financial data from SEC EDGAR."""

    symbol: str
    cik: str
    concept: str  # XBRL concept (e.g. Revenues, NetIncomeLoss)
    value: Decimal
    unit: str
    period_start: date
    period_end: date
    form: str  # Filing form: 10-K, 10-Q
    fiscal_year: int
    fiscal_quarter: int | None = None
    provider: str = "sec_edgar"
    filed_date: date | None = None  # when the fact became public (point-in-time anchor)
    accession: str | None = None  # SEC accession number of the source filing


@dataclass
class MacroIndicator:
    """Macroeconomic indicator data from FRED."""

    series_id: str
    series_name: str
    value: Decimal | None
    date: date
    unit: str = ""
    frequency: str = ""
    provider: str = "fred"


class BaseProvider(ABC):
    """Abstract base class for all price/quote data providers."""

    name: str = "base"
    priority: int = 0
    daily_limit: int | None = None
    minute_limit: int | None = None
    supports_batch: bool = False
    supported_exchanges: list[str] = []  # Exchanges this provider covers
    supports_realtime: bool = True  # Can provide real-time/intraday quotes
    supports_historical: bool = True  # Can provide historical daily data

    @abstractmethod
    async def get_quote(self, symbol: str) -> QuoteData | None:
        """Get current quote for a single symbol."""
        pass

    @abstractmethod
    async def get_quotes_batch(self, symbols: list[str]) -> list[QuoteData]:
        """Get quotes for multiple symbols. Default implementation calls get_quote for each."""
        pass

    @abstractmethod
    async def get_historical(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[HistoricalData]:
        """Get historical daily prices for a symbol."""
        pass

    @abstractmethod
    async def get_stock_info(self, symbol: str) -> StockInfo | None:
        """Get stock information (name, sector, etc.)."""
        pass

    @abstractmethod
    async def search_stocks(self, query: str) -> list[StockInfo]:
        """Search for stocks by name or symbol."""
        pass

    async def is_available(self) -> bool:
        """Check if the provider is available (override for custom checks)."""
        return True


class EnrichmentProvider(ABC):  # noqa: B024 — marker base, no abstract members
    """Abstract base class for enrichment-only data providers (EDGAR, FRED)."""

    name: str = "enrichment_base"
    supported_exchanges: list[str] = []

    async def is_available(self) -> bool:
        """Check if the provider is available."""
        return True


@dataclass
class ChineseStockNameData:
    """Authoritative Chinese stock name mapping returned by Chinese-native providers."""

    symbol: str  # Yahoo Finance format: 600519.SS / 000858.SZ
    code: str  # Bare 6-digit code: 600519 / 000858
    name_cn: str  # Chinese name: 贵州茅台 / 五粮液
    exchange: str  # SSE or SZSE
    provider: str  # 'akshare' or 'tushare'


class ChineseNameProvider(ABC):
    """Mixin for providers that supply authoritative Chinese stock names.

    Implemented by AKShareProvider and TuShareProvider.
    The orchestrator calls ``get_all_chinese_names()`` on every registered
    ChineseNameProvider to populate/refresh the ``chinese_stock_names`` table.
    AKShare is the primary source; TuShare fills any gaps.
    """

    @abstractmethod
    async def get_all_chinese_names(self) -> list[ChineseStockNameData]:
        """Fetch the complete Chinese stock name registry in a single bulk call.

        Returns a list of ChineseStockNameData covering all A-share stocks
        available from this provider.  The caller merges results across
        providers, with first-provider-wins semantics (AKShare has priority).
        """
        pass
