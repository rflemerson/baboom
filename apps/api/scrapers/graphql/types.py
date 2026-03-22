"""GraphQL types exposed for scraper-managed entities."""

import json
from typing import cast

import strawberry
from strawberry import auto
from strawberry.django import type as django_type

from core.models import Store
from scrapers.models import ScrapedItem


@django_type(ScrapedItem)
class ScrapedItemType:
    """GraphQL type for ScrapedItem."""

    id: auto
    store_slug: auto
    external_id: auto
    name: auto
    status: auto
    price: auto
    stock_status: auto

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
    def product_store_id(self) -> int | None:
        """Return linked ProductStore id if exists."""
        item = cast("ScrapedItem", self)
        return item.product_store_id

    @strawberry.field
    def linked_product_id(self) -> int | None:
        """Return linked Product id if exists."""
        item = cast("ScrapedItem", self)
        if item.product_store:
            return item.product_store.product_id
        return None

    @strawberry.field
    def store_name(self) -> str:
        """Get the display name of the store."""
        store = Store.objects.filter(name=self.store_slug).first()
        if store:
            return store.display_name

        return self.store_slug.replace("_", " ").title()
