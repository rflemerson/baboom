"""Contracts exchanged between scraper normalization and persistence."""

from __future__ import annotations

import decimal
import re
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Keep Decimal in runtime globals: Pydantic resolves this annotation at import time.
_PYDANTIC_RUNTIME_TYPES = (Decimal,)


class StockReading(StrEnum):
    """What a store said about availability, in this layer's own words.

    The values match ``offers.models.StockStatus`` because the vocabulary is
    the same one; the translation lives in persistence so a normalizer never
    has to import the ORM.
    """

    AVAILABLE = "A"
    LAST_UNITS = "L"
    OUT_OF_STOCK = "O"
    PREORDER = "P"
    BACKORDER = "B"
    UNKNOWN = "U"


# How a buyable unit is reached on its page. Closed on purpose: an unknown
# kind is a normalizer inventing a mechanism the curator cannot follow.
SelectionKind = Literal["query_parameter", "path", "fragment", "form_option"]


class VariantOption(BaseModel):
    """One option the store published for a buyable unit, verbatim."""

    name: str
    value: str


class VariantSelection(BaseModel):
    """How to reach a buyable unit on its page."""

    kind: SelectionKind
    parameters: dict[str, str] = Field(default_factory=dict)


class VariantContext(BaseModel):
    """Where to look, never what was found.

    Curation reads mass, flavor, and composition from the label, so a guess
    recorded here would compete with it.
    """

    schema_version: Literal[1] = 1
    provider: str = ""
    provider_product_id: str = ""
    provider_variant_id: str = ""
    title: str = ""
    options: list[VariantOption] = Field(default_factory=list)
    selection: VariantSelection | None = None


class SellerInput(BaseModel):
    """The seller of a unit, as the source names it.

    On a platform without third-party sellers the normalizer states the
    channel owner; a marketplace states the seller's own id.
    """

    external_id: str = ""
    name: str = ""
    is_channel_owner: bool = False


class MarketInput(BaseModel):
    """The market a spider reads, as its configuration declares it."""

    namespace: str
    channel_name: str
    channel_kind: Literal["independent_store", "marketplace", "app"]
    adapter: str
    country: str
    currency: str
    timezone: str
    tax_inclusion: Literal["included", "excluded", "unknown"] = "unknown"


class PriceContextInput(BaseModel):
    """Closed observation restrictions; absent dimensions remain unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    program_id: int | None = Field(default=None, ge=1)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    subdivision: str | None = None
    postal_code: str | None = None
    subscription: bool | None = None


class PriceInput(BaseModel):
    """One value a source states for a unit, with what it means.

    ``payment_scope`` ``unknown`` is not ``any``; ``cash`` is one immediate
    payment whose method the source does not name; ``method`` names it in
    ``payment_method`` (a code such as ``pix``, ``credit_card``, ``boleto``).
    """

    model_config = ConfigDict(extra="forbid")
    quantity_min: int = Field(default=1, ge=1)
    quantity_max: int | None = Field(default=None, ge=1)
    amount_basis: Literal["unit", "line", "order"] = "unit"
    currency: str = Field(default="", pattern=r"^([A-Z]{3})?$")
    context: PriceContextInput = Field(default_factory=PriceContextInput)

    @model_validator(mode="after")
    def valid_quantity_range(self) -> PriceInput:
        """Reject an impossible quantity interval."""
        if self.quantity_max is not None and self.quantity_max < self.quantity_min:
            msg = "quantity_max must be at least quantity_min"
            raise ValueError(msg)
        return self

    role: Literal["payable", "reference"]
    amount: Decimal
    source_field: str
    payment_scope: Literal["unknown", "any", "cash", "method"] = "unknown"
    payment_method: str = ""
    payment_label_raw: str = ""
    payment_provider_raw: str = ""
    installment_count: int | None = None
    installment_amount: Decimal | None = None
    interest: Literal["yes", "no", "unknown"] = "unknown"
    capture_stage: Literal["catalog", "product_page", "cart", "checkout"] = "catalog"
    evidence_level: Literal[
        "advertised",
        "observed_in_catalog",
        "quoted_for_context",
    ] = "observed_in_catalog"
    composition: Literal["known", "partial", "unknown"] = "unknown"
    included_adjustments: list[dict[str, str]] = Field(default_factory=list)


class CoverageInput(BaseModel):
    """How completely a page's normalizer read one dimension of it."""

    dimension: Literal[
        "variants",
        "sellers",
        "offers",
        "payment_prices",
        "availability",
        "pagination",
    ]
    status: Literal["complete", "partial", "failed", "access_unavailable"]
    reason: str = ""


class ScrapedOfferInput(BaseModel):
    """One independently buyable and priced unit from a product page."""

    external_id: str
    offer_url: str = ""
    name: str = ""
    price: Decimal | None = None
    stock_status: StockReading = StockReading.UNKNOWN
    stock_quantity: int | None = None
    sku: str = ""
    ean: str = ""
    variant_context: VariantContext
    seller: SellerInput | None = None
    featured: bool = False
    prices: list[PriceInput] = Field(default_factory=list)


class ScrapedProductInput(BaseModel):
    """One source page and all independently buyable units found on it."""

    store_slug: str
    provider: str
    provider_product_id: str
    page_url: str
    category: str = ""
    api_context: str | dict = ""
    offers: list[ScrapedOfferInput]
    # Only a dimension read completely may establish absence within the page.
    coverage: list[CoverageInput] = Field(default_factory=list)
    market: MarketInput | None = None
    adapter_version: str = "1"

    def is_complete(self, dimension: str) -> bool:
        """Whether the normalizer read this dimension of the page completely."""
        return any(
            item.dimension == dimension and item.status == "complete"
            for item in self.coverage
        )


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
    stock_status: StockReading = StockReading.UNKNOWN
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
