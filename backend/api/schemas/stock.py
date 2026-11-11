"""Pydantic schemas for Stock endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StockBase(BaseModel):
    """Base stock schema."""

    symbol: str
    name: str
    name_cn: str | None = None
    exchange: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None


class StockCreate(StockBase):
    """Schema for creating a stock."""

    pass


class StockResponse(StockBase):
    """Schema for stock response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class StockWithQuote(StockResponse):
    """Stock with latest quote data."""

    price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    volume: int | None = None
    quote_timestamp: datetime | None = None


class StockSearchResult(BaseModel):
    """Schema for stock search result."""

    symbol: str
    name: str
    name_cn: str | None = None
    exchange: str | None = None
