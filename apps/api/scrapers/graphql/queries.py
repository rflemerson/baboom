"""Authenticated queries for local product review clients."""

from __future__ import annotations

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.selectors import (
    catalog_brands,
    catalog_candidates,
    catalog_categories,
    catalog_tags,
    review_extraction,
    review_item,
    review_items,
)

from .types import (
    CatalogCandidateType,
    CatalogChoiceType,
    ScrapedItemExtractionType,
    ScrapedItemType,
)


@strawberry.type
class ScrapersQuery:
    """Read-only discovery and resume operations for product review."""

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def review_queue(
        self,
        status: str | None = "queued",
        search: str = "",
        limit: int = 20,
    ) -> list[ScrapedItemType]:
        """List review items without reserving them."""
        return list(review_items(status=status, search=search, limit=limit))

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def review_item(self, item_id: int) -> ScrapedItemType | None:
        """Read one item by id without changing its state."""
        return review_item(item_id)

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def review_extraction(self, item_id: int) -> ScrapedItemExtractionType | None:
        """Read the current staged extraction for an item."""
        extraction = review_extraction(item_id)
        return (
            ScrapedItemExtractionType.from_model(extraction)
            if extraction is not None
            else None
        )

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def catalog_candidates(
        self,
        search: str = "",
        ean: str = "",
        limit: int = 20,
    ) -> list[CatalogCandidateType]:
        """Search all canonical products before creating a duplicate."""
        return [
            CatalogCandidateType.from_model(product)
            for product in catalog_candidates(search=search, ean=ean, limit=limit)
        ]

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def catalog_brands(
        self,
        search: str = "",
        limit: int = 50,
    ) -> list[CatalogChoiceType]:
        """List brand identifiers accepted by product approval."""
        return [
            CatalogChoiceType.from_model(item) for item in catalog_brands(search, limit)
        ]

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def catalog_categories(
        self,
        search: str = "",
        limit: int = 50,
    ) -> list[CatalogChoiceType]:
        """List category identifiers accepted by product approval."""
        return [
            CatalogChoiceType.from_model(item)
            for item in catalog_categories(search, limit)
        ]

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def catalog_tags(
        self,
        search: str = "",
        limit: int = 50,
    ) -> list[CatalogChoiceType]:
        """List tag identifiers accepted by product approval."""
        return [
            CatalogChoiceType.from_model(item) for item in catalog_tags(search, limit)
        ]
