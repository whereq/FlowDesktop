"""Pydantic schemas for Quote endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class QuoteBase(BaseModel):
    """Base quote schema."""

    price: float
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    change: float | None = None
    change_percent: float | None = None


class QuoteResponse(QuoteBase):
    """Schema for quote response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    provider: str | None = None
    timestamp: datetime
    created_at: datetime


class QuoteWithSymbol(QuoteResponse):
    """Quote with stock symbol."""

    symbol: str
    name: str


class HistoricalPriceResponse(BaseModel):
    """Schema for historical price response."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adj_close: float | None = None
    volume: int | None = None


class MarketOverview(BaseModel):
    """Market overview with indices and movers."""

    indices: list["IndexQuote"]
    top_gainers: list["MoverStock"]
    top_losers: list["MoverStock"]
    most_active: list["MoverStock"]
    last_updated: datetime


class IndexQuote(BaseModel):
    """Index quote for market overview."""

    symbol: str
    name: str
    price: float
    change: float | None = None
    change_percent: float | None = None


class MoverStock(BaseModel):
    """Stock mover for gainers/losers."""

    symbol: str
    name: str
    name_cn: str | None = None
    price: float
    change: float | None = None
    change_percent: float | None = None
    volume: int | None = None


class ProviderStatusResponse(BaseModel):
    """Provider status for monitoring."""

    name: str
    priority: int
    daily_limit: int | None = None
    daily_used: int
    minute_limit: int | None = None
    minute_used: int
    is_available: bool
    can_make_request: bool
