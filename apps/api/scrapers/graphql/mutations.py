"""Mutations for scraper control and item lifecycle operations."""

from __future__ import annotations

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.services import (
    ScrapedItemCheckoutService,
    ScrapedItemDiscardService,
    ScrapedItemErrorService,
    ScrapedItemLinkService,
    ScrapedItemSourcePageService,
    ScrapedItemVariantService,
)

from .inputs import (
    ScrapedItemCheckoutInput,
    ScrapedItemErrorInput,
    ScrapedItemLinkInput,
    ScrapedItemVariantInput,
)
from .types import ScrapedItemType

_STRAWBERRY_RUNTIME_TYPES = (
    ScrapedItemCheckoutInput,
    ScrapedItemErrorInput,
    ScrapedItemLinkInput,
    ScrapedItemVariantInput,
    ScrapedItemType,
)


@strawberry.type
class ScrapersMutation:
    """Mutations for scraper management."""

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def checkout_scraped_item(
        self,
        data: ScrapedItemCheckoutInput,
    ) -> ScrapedItemType | None:
        """Reserve one scraped item for agent processing."""
        return ScrapedItemCheckoutService().execute(data)

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def report_scraped_item_error(
        self,
        data: ScrapedItemErrorInput,
    ) -> bool:
        """Report an error for a scraped item."""
        return ScrapedItemErrorService().execute(
            item_id=data.item_id,
            message=data.message,
            is_fatal=data.is_fatal,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def discard_scraped_item(self, item_id: int, reason: str) -> bool:
        """Agent marks item as DISCARDED (e.g., T-shirt, not supplement)."""
        return ScrapedItemDiscardService().execute(item_id=item_id, reason=reason)

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def ensure_scraped_item_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> ScrapedItemType | None:
        """Ensure item has source page linked, creating page by URL when needed."""
        return ScrapedItemSourcePageService().ensure(
            item_id=item_id,
            url=url,
            store_slug=store_slug,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def link_scraped_item_to_product_store(
        self,
        data: ScrapedItemLinkInput,
    ) -> ScrapedItemType | None:
        """Explicitly link a scraped item to a chosen product store."""
        return ScrapedItemLinkService().execute(
            scraped_item_id=data.item_id,
            product_store_id=data.product_store_id,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def update_scraped_item_data(
        self,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ) -> ScrapedItemType | None:
        """Update mutable fields of a scraped item used by agents pipeline."""
        return ScrapedItemSourcePageService().update_item_data(
            item_id=item_id,
            name=name,
            source_page_url=source_page_url,
            store_slug=store_slug,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticatedWithAPIKey])
    def upsert_scraped_item_variant(
        self,
        data: ScrapedItemVariantInput,
    ) -> ScrapedItemType | None:
        """Create or update a variant ScrapedItem linked to the same source page."""
        return ScrapedItemVariantService().execute(data)
