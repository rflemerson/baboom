"""Input objects for scraper GraphQL mutations."""

import strawberry
from strawberry.scalars import JSON

_STRAWBERRY_RUNTIME_TYPES = (JSON,)


@strawberry.input
class ScrapedItemCheckoutInput:
    """Input for checking out scraped items for processing."""

    force: bool = False
    target_item_id: int | None = None


@strawberry.input
class ScrapedItemErrorInput:
    """Input for reporting scraped item processing failures."""

    item_id: int
    message: str
    is_fatal: bool = False


@strawberry.input
class ScrapedItemLinkInput:
    """Input for explicitly linking a scraped item to a product store."""

    item_id: int
    product_store_id: int


@strawberry.input
class AgentExtractionInput:
    """Input for staging one agent extraction for review."""

    origin_scraped_item_id: int
    source_page_id: int | None = None
    source_page_url: str = ""
    store_slug: str = ""
    image_report: str = ""
    product: JSON
