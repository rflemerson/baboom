"""GraphQL queries for scraper-facing workflows."""

from __future__ import annotations

from importlib import import_module
from typing import cast

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.models import ScrapedItem

scraper_types = import_module("scrapers.graphql.types")


@strawberry.type
class ScrapersQuery:
    """Queries for scraper-backed data used by agents."""

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def scraped_item(
        self,
        item_id: int,
    ) -> scraper_types.ScrapedItemType | None:
        """Get a scraped item by id."""
        item = ScrapedItem.objects.filter(id=item_id).first()
        return cast("scraper_types.ScrapedItemType | None", item)
