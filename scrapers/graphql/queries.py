from typing import cast

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.models import ScrapedItem

from .types import ScrapedItemType


@strawberry.type
class ScrapersQuery:
    """Queries for scraper-backed data used by agents."""

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def scraped_item(self, item_id: int) -> ScrapedItemType | None:
        """Get a scraped item by id."""
        item = ScrapedItem.objects.filter(id=item_id).first()
        return cast(ScrapedItemType | None, item)
