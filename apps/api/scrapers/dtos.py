"""Typed DTOs shared by scraper ingestion workflows."""

from __future__ import annotations

import decimal
import re
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ScrapedItem

_PYDANTIC_RUNTIME_TYPES = (decimal.Decimal,)

type JsonObject = dict[str, Any]


class ScrapedItemIngestionInput(BaseModel):
    """DTO for persisting scraped item snapshots."""

    GTIN_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^\d{8,14}$")

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

    @field_validator("ean", mode="before")
    @classmethod
    def normalize_ean(cls, value: object) -> str:
        """Keep only valid GTIN-like EAN values that fit the database field."""
        ean = str(value or "").strip()
        return ean if cls.GTIN_PATTERN.fullmatch(ean) else ""


class ExtractedMicronutrientInput(BaseModel):
    """Micronutrient extracted by the agent from a product page."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    value: float | None = None
    unit: str = ""


class ExtractedNutritionFactsInput(BaseModel):
    """Nullable nutrition facts extracted by the agent."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    description: str | None = None
    serving_size_grams: float | None = Field(
        default=None,
        alias="servingSizeGrams",
    )
    energy_kcal: float | None = Field(default=None, alias="energyKcal")
    proteins: float | None = None
    carbohydrates: float | None = None
    total_sugars: float | None = Field(default=None, alias="totalSugars")
    added_sugars: float | None = Field(default=None, alias="addedSugars")
    total_fats: float | None = Field(default=None, alias="totalFats")
    saturated_fats: float | None = Field(default=None, alias="saturatedFats")
    trans_fats: float | None = Field(default=None, alias="transFats")
    dietary_fiber: float | None = Field(default=None, alias="dietaryFiber")
    sodium: float | None = None
    micronutrients: list[ExtractedMicronutrientInput] = Field(default_factory=list)


class ExtractedProductInput(BaseModel):
    """Recursive product tree extracted by the agent."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str | None = None
    brand_name: str | None = Field(default=None, alias="brandName")
    ean: str | None = ""
    weight_grams: int | None = Field(default=None, alias="weightGrams")
    packaging: str | None = ""
    quantity: int | None = None
    description: str | None = ""
    category_hierarchy: list[str] = Field(
        default_factory=list,
        alias="categoryHierarchy",
    )
    tags_hierarchy: list[list[str]] = Field(
        default_factory=list,
        alias="tagsHierarchy",
    )
    flavor_names: list[str] = Field(default_factory=list, alias="flavorNames")
    variant_name: str | None = Field(default=None, alias="variantName")
    nutrition_facts: ExtractedNutritionFactsInput | None = Field(
        default=None,
        alias="nutritionFacts",
    )
    children: list[ExtractedProductInput] = Field(default_factory=list)


class AgentExtractionSubmitInput(BaseModel):
    """DTO for staging one agent extraction against a scraped item."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    origin_scraped_item_id: int = Field(alias="originScrapedItemId")
    source_page_id: int | None = Field(default=None, alias="sourcePageId")
    source_page_url: str = Field(default="", alias="sourcePageUrl")
    store_slug: str = Field(default="", alias="storeSlug")
    image_report: str = Field(default="", alias="imageReport")
    product: ExtractedProductInput

    def product_payload(self) -> JsonObject:
        """Return the validated product tree using the agent-facing aliases."""
        return self.product.model_dump(by_alias=True, exclude_none=True)
