"""Typed DTOs shared by scraper ingestion workflows."""

from __future__ import annotations

from importlib import import_module

from pydantic import BaseModel

from .models import ScrapedItem

decimal = import_module("decimal")


class ProductIngestionInput(BaseModel):
    """DTO for saving scraped products."""

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
