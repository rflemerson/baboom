"""Typed DTOs shared by scraper ingestion workflows."""

from __future__ import annotations

import decimal

from pydantic import BaseModel

from .models import ScrapedItem

_PYDANTIC_RUNTIME_TYPES = (decimal.Decimal,)


class ScrapedItemIngestionInput(BaseModel):
    """DTO for persisting scraped item snapshots."""

    store_slug: str
    external_id: str
    url: str = ""
    name: str = ""
    price: str | float | decimal.Decimal | None = None
    stock_quantity: int | None = None
    stock_status: str = ScrapedItem.StockStatus.AVAILABLE
    ean: str = ""
    sku: str = ""
    pid: str = ""
    category: str = ""
