"""GraphQL types exposed for scraper-managed entities."""

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
    def source_page_raw_content(self) -> str:
        """Return raw structured context saved by scraper."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return item.source_page.raw_content or ""
        return ""

    @strawberry.field
    def source_page_content_type(self) -> str:
        """Return source page content type (HTML/JSON)."""
        item = cast("ScrapedItem", self)
        if item.source_page:
            return item.source_page.content_type
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
