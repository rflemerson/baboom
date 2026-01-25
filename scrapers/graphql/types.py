from strawberry import auto
from strawberry.django import type as django_type

from scrapers.models import ScrapedItem


@django_type(ScrapedItem)
class ScrapedItemType:
    id: auto
    store_slug: auto
    product_link: auto
    external_id: auto
