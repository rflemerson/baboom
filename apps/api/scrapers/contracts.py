"""Contracts exchanged between scraper normalization and persistence."""

from __future__ import annotations

import decimal
import re
from decimal import Decimal
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator

from offers.models import StockStatus

# Keep Decimal in runtime globals: Pydantic resolves this annotation at import time.
_PYDANTIC_RUNTIME_TYPES = (Decimal,)


class VariantOption(BaseModel):
    """One option the store published for a buyable unit, verbatim."""

    name: str
    value: str


class VariantSelection(BaseModel):
    """How to reach a buyable unit on its page."""

    kind: str
    parameters: dict[str, str] = Field(default_factory=dict)


class VariantContext(BaseModel):
    """Where to look, never what was found; curation reads mass, flavor, and
    composition from the label so guesses here do not compete with it."""

    schema_version: Literal[1] = 1
    provider: str = ""
    provider_product_id: str = ""
    provider_variant_id: str = ""
    title: str = ""
    options: list[VariantOption] = Field(default_factory=list)
    selection: VariantSelection | None = None


class ScrapedOfferInput(BaseModel):
    """One independently buyable and priced unit from a product page."""

    external_id: str
    offer_url: str = ""
    name: str = ""
    price: Decimal | None = None
    stock_status: str = StockStatus.AVAILABLE
    stock_quantity: int | None = None
    sku: str = ""
    ean: str = ""
    variant_context: VariantContext


class ScrapedProductInput(BaseModel):
    """One source page and all independently buyable units found on it."""

    store_slug: str
    provider: str
    provider_product_id: str
    page_url: str
    category: str = ""
    api_context: str | dict = ""
    offers: list[ScrapedOfferInput]


class ScrapedItemIngestionInput(BaseModel):
    """DTO for persisting scraped item snapshots."""

    GTIN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\d{8,14}$")

    store_slug: str
    external_id: str
    page_url: str = ""
    offer_url: str = ""
    variant_context: VariantContext = VariantContext()
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
