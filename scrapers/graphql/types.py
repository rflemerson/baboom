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
    product_link: auto
    external_id: auto
    price: auto
    stock_status: auto

    @strawberry.field
    def store_name(self) -> str:
        """Get the display name of the store."""
        store = Store.objects.filter(name=self.store_slug).first()
        if store:
            return store.display_name

        # Fallback to title-cased slug if Store object doesn't exist yet
        return self.store_slug.replace("_", " ").title()
