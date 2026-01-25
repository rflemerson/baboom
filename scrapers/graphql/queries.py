from typing import cast

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from scrapers.models import ScrapedItem

from .types import ScrapedItemType


@strawberry.type
class ScrapersQuery:
    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def pending_scraped_items(self, limit: int = 10) -> list[ScrapedItemType]:
        """
        Work queue for the Agent.
        Returns items with 'NEW' status that need to be processed.
        """
        qs = ScrapedItem.objects.filter(
            status=ScrapedItem.Status.NEW, product_link__startswith="http"
        ).order_by("updated_at")[:limit]

        return cast(list[ScrapedItemType], qs)
