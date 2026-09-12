"""Typed DTOs shared by scraper ingestion workflows."""

from __future__ import annotations

import decimal
import re
from typing import ClassVar

from pydantic import BaseModel, field_validator

from offers.models import StockStatus

_PYDANTIC_RUNTIME_TYPES = (decimal.Decimal,)


class ScrapedItemIngestionInput(BaseModel):
    """DTO for persisting scraped item snapshots."""

    GTIN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\d{8,14}$")

    store_slug: str
    external_id: str
    url: str = ""
    name: str = ""
    price: str | float | decimal.Decimal | None = None
    stock_quantity: int | None = None
    stock_status: str = StockStatus.AVAILABLE
    ean: str = ""
    sku: str = ""
    pid: str = ""
    category: str = ""

    @field_validator("ean", mode="before")
    @classmethod
    def normalize_ean(cls, value: object) -> str:
        """Keep only valid GTIN-like EAN values that fit the database field."""
        ean = str(value or "").strip()
        return ean if cls.GTIN_PATTERN.fullmatch(ean) else ""
