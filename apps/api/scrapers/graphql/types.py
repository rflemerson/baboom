"""GraphQL types exposed for scraper-managed entities."""

import json
from datetime import datetime
from decimal import Decimal
from typing import cast

import strawberry
from strawberry import auto
from strawberry.django import type as django_type
from strawberry.scalars import JSON

from baboom.utils import ValidationError
from core.models import Brand, Category, Product, Tag
from core.units import DISPLAY_MASS_UNIT, from_canonical
from scrapers.images import image_urls
from scrapers.models import ScrapedItem, ScrapedItemExtraction

_STRAWBERRY_RUNTIME_TYPES = (datetime, Decimal, JSON, ValidationError)


@django_type(ScrapedItem)
class ScrapedItemType:
    """GraphQL type for ScrapedItem.

    Identity, descriptive and price fields are resolved from the merchant offer,
    keeping the agent-facing contract stable after the offer split.
    """

    id: auto
    status: auto
    last_attempt_at: auto
    updated_at: auto

    @strawberry.field
    def store_slug(self) -> str:
        """Return the store slug from the merchant offer."""
        item = cast("ScrapedItem", self)
        return item.offer.store_slug

    @strawberry.field
    def external_id(self) -> str:
        """Return the merchant identifier from the merchant offer."""
        item = cast("ScrapedItem", self)
        return item.offer.external_id

    @strawberry.field
    def name(self) -> str:
        """Return the product name from the merchant offer."""
        item = cast("ScrapedItem", self)
        return item.offer.name

    @strawberry.field
    def price(self) -> Decimal | None:
        """Return the latest observed price from the merchant offer."""
        item = cast("ScrapedItem", self)
        return item.offer.current_price

    @strawberry.field
    def stock_status(self) -> str:
        """Return the latest observed stock status from the merchant offer."""
        item = cast("ScrapedItem", self)
        return item.offer.current_stock_status

    @strawberry.field
    def product_link(self) -> str:
        """Return the product page URL for review clients."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return item.source_page.url
        return ""

    @strawberry.field
    def source_page_url(self) -> str:
        """Explicit URL field for page-first pipelines."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return item.source_page.url
        return ""

    @strawberry.field
    def source_page_id(self) -> int | None:
        """Return the stable identifier of the stored source page."""
        item = cast("ScrapedItem", self)
        return item.source_page_id

    @strawberry.field
    def source_page_api_context(self) -> str:
        """Return API-backed product context saved by the scraper."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return json.dumps(item.source_page.api_context or {}, ensure_ascii=False)
        return ""

    @strawberry.field
    def source_page_context(self) -> JSON:
        """Return API-backed context as JSON for new review clients."""
        item = cast("ScrapedItem", self)
        return item.source_page.api_context if item.source_page else {}

    @strawberry.field
    def source_page_html_structured_data(self) -> str:
        """Return schema.org metadata parsed from the page HTML."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return json.dumps(
                item.source_page.html_structured_data or {},
                ensure_ascii=False,
            )
        return ""

    @strawberry.field
    def source_page_structured_data(self) -> JSON:
        """Return parsed HTML metadata as JSON for new review clients."""
        item = cast("ScrapedItem", self)
        return item.source_page.html_structured_data if item.source_page else {}

    @strawberry.field
    def source_page_raw_html(self) -> str:
        """Return the full rendered page HTML captured by the scraper."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return item.source_page.raw_html or ""
        return ""

    @strawberry.field
    def store_name(self) -> str:
        """Return a display label derived from the offer's store slug."""
        item = cast("ScrapedItem", self)
        store_slug = item.offer.store_slug
        return store_slug.replace("_", " ").title()

    @strawberry.field
    def ean(self) -> str:
        """Return the merchant EAN used for duplicate candidate lookup."""
        item = cast("ScrapedItem", self)
        return item.offer.ean

    @strawberry.field
    def category(self) -> str:
        """Return the merchant category label."""
        item = cast("ScrapedItem", self)
        return item.offer.category

    @strawberry.field
    def image_urls(self) -> list[str]:
        """Return stable, de-duplicated image URLs from stored page context."""
        item = cast("ScrapedItem", self)
        if item.source_page is None:
            return []
        return image_urls(
            [item.source_page.api_context, item.source_page.html_structured_data],
            base_url=item.source_page.url,
        )


@strawberry.type
class ScrapedItemExtractionType:
    """GraphQL type for staged agent extractions."""

    id: int
    scraped_item_id: int
    source_page_id: int
    image_report: str
    extracted_product: JSON
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, extraction: ScrapedItemExtraction) -> ScrapedItemExtractionType:
        """Build a GraphQL type from a persisted extraction."""
        return cls(
            id=extraction.id,
            scraped_item_id=extraction.scraped_item_id,
            source_page_id=extraction.source_page_id,
            image_report=extraction.image_report,
            extracted_product=extraction.extracted_product,
            created_at=extraction.created_at,
            updated_at=extraction.updated_at,
        )


@strawberry.type
class ScrapedItemExtractionResult:
    """Result for staging agent extractions."""

    extraction: ScrapedItemExtractionType | None = None
    errors: list[ValidationError] | None = None


@strawberry.type
class ScrapedItemResult:
    """Result for a validated review state transition."""

    item: ScrapedItemType | None = None
    errors: list[ValidationError] | None = None


@strawberry.type
class CatalogCandidateType:
    """Compact canonical product returned during duplicate resolution."""

    id: int
    name: str
    brand_id: int
    brand_name: str
    category_id: int | None
    category_name: str
    ean: str
    net_mass: float | None
    mass_unit: str
    packaging: str
    is_published: bool

    @classmethod
    def from_model(cls, product: Product) -> CatalogCandidateType:
        """Build a candidate without exposing manager-only model internals."""
        return cls(
            id=product.id,
            name=product.name,
            brand_id=product.brand_id,
            brand_name=product.brand.display_name,
            category_id=product.category_id,
            category_name=product.category.name if product.category else "",
            ean=product.ean or "",
            net_mass=(
                None
                if product.net_mass is None
                else float(from_canonical(product.net_mass, DISPLAY_MASS_UNIT))
            ),
            mass_unit=DISPLAY_MASS_UNIT,
            packaging=product.packaging,
            is_published=product.is_published,
        )


@strawberry.type
class CatalogChoiceType:
    """Identifier and name for catalog taxonomy choices."""

    id: int
    name: str

    @classmethod
    def from_model(cls, choice: Brand | Category | Tag) -> CatalogChoiceType:
        """Build a compact choice from one catalog reference model."""
        display_name = choice.display_name if isinstance(choice, Brand) else choice.name
        return cls(id=choice.id, name=display_name)


@strawberry.type
class ScrapedItemApprovalResult:
    """Result of an explicit catalog approval."""

    product: CatalogCandidateType | None = None
    errors: list[ValidationError] | None = None
