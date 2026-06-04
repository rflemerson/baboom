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
        """Backward-compatible URL field used by agent workers."""
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
        """Return source page id for storage bucket mapping."""
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
    def source_page_html_structured_data(self) -> str:
        """Return structured metadata extracted from the page HTML."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return json.dumps(
                item.source_page.html_structured_data or {},
                ensure_ascii=False,
            )
        return ""

    @strawberry.field
    def store_name(self) -> str:
        """Return a display label derived from the offer's store slug."""
        item = cast("ScrapedItem", self)
        store_slug = item.offer.store_slug
        return store_slug.replace("_", " ").title()


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
