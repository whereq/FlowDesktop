"""SEC EDGAR enrichment provider for fundamental financial data."""

import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal

import aiohttp

from flowdesk_collector.providers.base import EnrichmentProvider, FundamentalData

logger = logging.getLogger(__name__)

# EDGAR requires a User-Agent identifying the application and contact email
# The SEC asks automated clients to identify themselves with a contact address.
# Override with SEC_USER_AGENT="Your Name you@example.com".
USER_AGENT = os.getenv("SEC_USER_AGENT", "FlowDesktop flowdesktop@example.com")

# XBRL concepts to extract from company facts (us-gaap namespace).
#
# The companyfacts JSON carries every concept a company has ever tagged, so
# widening this list costs nothing to download — it only decides what we
# keep.  Each concept here is one that a large share of filers reports, and
# each one is something the set did not already let a consumer compute:
# margins need the cost line, returns on capital need the invested-capital
# lines, leverage needs the current/debt split, and shareholder returns
# need capex, buybacks and dividends paid.
#
# Where two tags carry the same number for the same filer (the pre- and
# post-ASC-606 revenue tags, the two cost-of-revenue tags, the two D&A
# tags) both are kept and the API folds them into one line item — see
# data_api/routers/equities.py::_FUND_CONCEPTS, which must mirror this
# list exactly.
XBRL_CONCEPTS = [
    # ── Income statement ───────────────────────────────────────────────
    "Revenues",
    # Modern filers (ASC 606) report top-line under this tag, not "Revenues" —
    # without it, revenue is null for AAPL/MSFT & co. The API maps both to `revenue`.
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    # The two cost-of-revenue tags: retail filers use the first, most
    # others the second.  Both fold into `cost_of_revenue`.
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "GrossProfit",
    "OperatingExpenses",
    "SellingGeneralAndAdministrativeExpense",
    "ResearchAndDevelopmentExpense",
    "OperatingIncomeLoss",
    "NonoperatingIncomeExpense",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeTaxExpenseBenefit",
    "InterestExpense",
    "InvestmentIncomeInterest",
    "NetIncomeLoss",
    # ── Per-share ──────────────────────────────────────────────────────
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "CommonStockDividendsPerShareDeclared",
    # The cash-paid dividend tag, for filers that use it instead.
    "CommonStockDividendsPerShareCashPaid",
    # ── Balance sheet ──────────────────────────────────────────────────
    "Assets",
    "AssetsCurrent",
    "Liabilities",
    "LiabilitiesCurrent",
    "StockholdersEquity",
    "RetainedEarningsAccumulatedDeficit",
    "CashAndCashEquivalentsAtCarryingValue",
    "AccountsReceivableNetCurrent",
    "InventoryNet",
    "AccountsPayableCurrent",
    "PropertyPlantAndEquipmentNet",
    "Goodwill",
    "IntangibleAssetsNetExcludingGoodwill",
    "LongTermDebt",
    "LongTermDebtCurrent",
    "CommonStockSharesOutstanding",
    # ── Cash-flow statement ────────────────────────────────────────────
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    # The two D&A tags — together they cover nearly every filer.
    "DepreciationDepletionAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "ShareBasedCompensation",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsOfDividends",
    "PaymentsForRepurchaseOfCommonStock",
]

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


class SecEdgarProvider(EnrichmentProvider):
    """SEC EDGAR enrichment provider.

    Fetches fundamental financial data from XBRL filings.
    No API key required; User-Agent header is mandatory.
    Enrichment-only: not part of the main price collection scheduler.
    """

    name = "sec_edgar"
    supported_exchanges = ["NYSE", "NASDAQ"]  # US exchanges only

    def __init__(self):
        self._cik_map: dict[str, int] = {}  # ticker -> CIK mapping cache

    async def is_available(self) -> bool:
        """EDGAR is always available (no key required)."""
        return True

    def _headers(self) -> dict:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}

    async def _load_cik_map(self) -> dict[str, int]:
        """Download and cache the CIK lookup map from SEC."""
        if self._cik_map:
            return self._cik_map

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(TICKERS_URL, headers=self._headers()) as response,
            ):
                if response.status != 200:
                    logger.error(
                        "CIK map fetch returned non-200 status",
                        extra={
                            "operation": "stock_info",
                            "provider": self.name,
                            "error_type": "http_error",
                        },
                    )
                    return {}

                data = await response.json(content_type=None)
                # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, ...}
                mapping: dict[str, int] = {}
                for entry in data.values():
                    ticker = entry.get("ticker", "").upper()
                    cik = entry.get("cik_str")
                    if ticker and cik:
                        mapping[ticker] = int(cik)

                self._cik_map = mapping
                logger.info(f"SEC EDGAR: loaded {len(mapping)} CIK mappings")
                return mapping

        except Exception:
            logger.error(
                "CIK map fetch failed",
                extra={
                    "operation": "stock_info",
                    "provider": self.name,
                    "error_type": "unknown_error",
                },
            )
            return {}

    async def get_cik(self, symbol: str) -> int | None:
        """Resolve a ticker symbol to its SEC CIK number."""
        mapping = await self._load_cik_map()
        return mapping.get(symbol.upper())

    async def get_fundamentals(self, symbol: str) -> list[FundamentalData]:
        """Fetch fundamental data for a symbol from SEC EDGAR XBRL facts.

        Returns a list of FundamentalData records covering key financial metrics
        extracted from 10-K and 10-Q filings.
        """
        cik = await self.get_cik(symbol)
        if not cik:
            logger.debug(f"SEC EDGAR: no CIK found for {symbol}")
            return []

        cik_str = f"{cik:010d}"
        url = COMPANY_FACTS_URL.format(cik=cik)

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers=self._headers()) as response,
            ):
                if response.status == 404:
                    logger.debug(f"SEC EDGAR: no filing data for CIK {cik} ({symbol})")
                    return []
                if response.status != 200:
                    logger.warning(
                        "Company facts fetch returned non-200 status",
                        extra={
                            "operation": "stock_info",
                            "provider": self.name,
                            "symbol": symbol,
                            "error_type": "http_error",
                        },
                    )
                    return []

                data = await response.json(content_type=None)

        except Exception:
            logger.error(
                "Fundamentals fetch failed",
                extra={
                    "operation": "stock_info",
                    "provider": self.name,
                    "symbol": symbol,
                    "error_type": "unknown_error",
                },
            )
            return []

        # Be polite to SEC servers
        await asyncio.sleep(0.5)

        results: list[FundamentalData] = []
        facts = data.get("facts", {})

        # XBRL facts live under us-gaap namespace
        us_gaap = facts.get("us-gaap", {})

        for concept in XBRL_CONCEPTS:
            concept_data = us_gaap.get(concept)
            if not concept_data:
                continue

            units_map = concept_data.get("units", {})
            # Units can be USD, shares, USD/shares, etc.
            for unit, entries in units_map.items():
                for entry in entries:
                    # Only include annual (10-K) and quarterly (10-Q) filings
                    form = entry.get("form", "")
                    if form not in ("10-K", "10-Q"):
                        continue

                    val_raw = entry.get("val")
                    if val_raw is None:
                        continue

                    end_str = entry.get("end", "")
                    start_str = entry.get("start", "")
                    if not end_str:
                        continue

                    try:
                        period_end = datetime.strptime(end_str, "%Y-%m-%d").date()
                    except ValueError:
                        continue

                    try:
                        period_start = (
                            datetime.strptime(start_str, "%Y-%m-%d").date()
                            if start_str
                            else period_end
                        )
                    except ValueError:
                        period_start = period_end

                    # Determine fiscal year and quarter
                    fiscal_year = period_end.year
                    fiscal_quarter: int | None = None
                    if form == "10-Q":
                        month = period_end.month
                        if month <= 3:
                            fiscal_quarter = 1
                        elif month <= 6:
                            fiscal_quarter = 2
                        elif month <= 9:
                            fiscal_quarter = 3
                        else:
                            fiscal_quarter = 4

                    try:
                        value = Decimal(str(val_raw))
                    except Exception:
                        continue

                    # Point-in-time anchor: when this fact was filed (became public).
                    filed_date = None
                    filed_str = entry.get("filed", "")
                    if filed_str:
                        try:
                            filed_date = datetime.strptime(filed_str, "%Y-%m-%d").date()
                        except ValueError:
                            filed_date = None

                    results.append(
                        FundamentalData(
                            symbol=symbol,
                            cik=cik_str,
                            concept=concept,
                            value=value,
                            unit=unit,
                            period_start=period_start,
                            period_end=period_end,
                            form=form,
                            fiscal_year=fiscal_year,
                            fiscal_quarter=fiscal_quarter,
                            provider=self.name,
                            filed_date=filed_date,
                            accession=entry.get("accn"),
                        )
                    )

        logger.info(f"SEC EDGAR: fetched {len(results)} fundamental records for {symbol}")
        return results
