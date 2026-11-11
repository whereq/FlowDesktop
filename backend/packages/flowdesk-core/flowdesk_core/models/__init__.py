"""Database models.

Importing this package registers every table on ``Base.metadata`` — that is
what Alembic autogenerate and the schema drift check rely on.
"""

from flowdesk_core.models.agent_schedule import AgentSchedule
from flowdesk_core.models.chat_quota import ChatQuota
from flowdesk_core.models.chinese_stock_name import ChineseStockName
from flowdesk_core.models.company_filing import CompanyFiling
from flowdesk_core.models.congress_trade import CongressTrade
from flowdesk_core.models.conversation import Conversation, Message
from flowdesk_core.models.crawl_coverage import CrawlCoverage
from flowdesk_core.models.crawler_run_log import CrawlerRunLog
from flowdesk_core.models.custom_agent import CustomAgent
from flowdesk_core.models.data_source import DataSource
from flowdesk_core.models.domain import Dataset, Domain, Entity, EntityIdentifier
from flowdesk_core.models.enrichment import FundamentalDataRecord, MacroIndicatorRecord
from flowdesk_core.models.historical import HistoricalPrice
from flowdesk_core.models.insider_transaction import InsiderTransaction
from flowdesk_core.models.investor_profile import InvestorProfile
from flowdesk_core.models.market_event import MarketEvent
from flowdesk_core.models.market_intelligence import (
    MarketNewsItem,
    MarketSignal,
    SectorIntelligence,
)
from flowdesk_core.models.message_feedback import MessageFeedback
from flowdesk_core.models.notification_prefs import NotificationPrefs
from flowdesk_core.models.proactive_insight_sent import ProactiveInsightSent
from flowdesk_core.models.provider import ProviderStatus
from flowdesk_core.models.provider_registry import ProviderRegistry
from flowdesk_core.models.pulse_tuning import PulseTuning
from flowdesk_core.models.push_subscription import PushSubscription
from flowdesk_core.models.quote import Quote
from flowdesk_core.models.retrieval_chunk import RetrievalChunk
from flowdesk_core.models.sectors import SectorTheme, StockRelationship, ThemeStock
from flowdesk_core.models.shadow_portfolio import ShadowTrade
from flowdesk_core.models.shared_analysis import SharedAnalysis
from flowdesk_core.models.short_interest import ShortInterest
from flowdesk_core.models.sim_account import SimAccount
from flowdesk_core.models.sim_fill import SimFill
from flowdesk_core.models.sim_order import SimOrder
from flowdesk_core.models.sim_position import SimPosition
from flowdesk_core.models.sim_snapshot import SimSnapshot
from flowdesk_core.models.stock import Stock
from flowdesk_core.models.translation import Translation
from flowdesk_core.models.user_alert import UserAlert
from flowdesk_core.models.user_memory import UserMemory
from flowdesk_core.models.user_notification import UserNotification
from flowdesk_core.models.user_profile import UserProfile
from flowdesk_core.models.watchlist import WatchlistItem

__all__ = [
    "AgentSchedule",
    "ChatQuota",
    "ChineseStockName",
    "CompanyFiling",
    "CongressTrade",
    "Conversation",
    "CrawlCoverage",
    "CrawlerRunLog",
    "CustomAgent",
    "DataSource",
    "Dataset",
    "Domain",
    "Entity",
    "EntityIdentifier",
    "FundamentalDataRecord",
    "HistoricalPrice",
    "InsiderTransaction",
    "InvestorProfile",
    "MacroIndicatorRecord",
    "MarketEvent",
    "MarketNewsItem",
    "MarketSignal",
    "Message",
    "MessageFeedback",
    "NotificationPrefs",
    "ProactiveInsightSent",
    "ProviderRegistry",
    "ProviderStatus",
    "PulseTuning",
    "PushSubscription",
    "Quote",
    "RetrievalChunk",
    "SectorIntelligence",
    "SectorTheme",
    "ShadowTrade",
    "SharedAnalysis",
    "ShortInterest",
    "SimAccount",
    "SimFill",
    "SimOrder",
    "SimPosition",
    "SimSnapshot",
    "Stock",
    "StockRelationship",
    "ThemeStock",
    "Translation",
    "UserAlert",
    "UserMemory",
    "UserNotification",
    "UserProfile",
    "WatchlistItem",
]
