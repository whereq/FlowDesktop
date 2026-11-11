"""Data provider implementations.

FlowDesktop ships with providers that need **no API key**:

* :class:`YahooFinanceProvider` — quotes and daily history (primary)
* :class:`StooqProvider` — historical prices, backup
* :class:`AKShareProvider` — mainland China listings (SSE / SZSE)
* :class:`SecEdgarProvider` — SEC filings and insider Form 4

Additional key-based providers can be added by dropping a new module in this
package and exporting it here — see ``docs/design-low-level-design.md``.
"""

from flowdesk_collector.providers._yahoo_exchange_base import YahooQuotaPool
from flowdesk_collector.providers.akshare import AKShareProvider
from flowdesk_collector.providers.base import (
    BaseProvider,
    ChineseNameProvider,
    ChineseStockNameData,
    EnrichmentProvider,
    FundamentalData,
    HistoricalData,
    MacroIndicator,
    QuoteData,
    StockInfo,
)
from flowdesk_collector.providers.sec_edgar import SecEdgarProvider
from flowdesk_collector.providers.stooq import StooqProvider
from flowdesk_collector.providers.yahoo import YahooFinanceProvider

__all__ = [
    # Base classes and data models
    "BaseProvider",
    "EnrichmentProvider",
    "ChineseNameProvider",
    "ChineseStockNameData",
    "QuoteData",
    "HistoricalData",
    "StockInfo",
    "FundamentalData",
    "MacroIndicator",
    # Price providers
    "YahooFinanceProvider",
    "StooqProvider",
    # Chinese market providers (SSE / SZSE)
    "AKShareProvider",
    # Enrichment providers
    "SecEdgarProvider",
    # Shared quota pool
    "YahooQuotaPool",
]
