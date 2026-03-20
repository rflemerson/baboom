"""Input objects for scraper GraphQL mutations."""

import strawberry


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
class ScrapedItemVariantInput:
    """Input for creating or updating scraped item variants."""

    origin_item_id: int
    external_id: str
    name: str
    page_url: str
    store_slug: str
    price: float | None = None
    stock_status: str | None = None


@strawberry.input
class ScrapedItemLinkInput:
    """Input for explicitly linking a scraped item to a product store."""

    item_id: int
    product_store_id: int
