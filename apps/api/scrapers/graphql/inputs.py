"""Input objects for scraper GraphQL mutations."""

import strawberry
from strawberry.scalars import JSON

_STRAWBERRY_RUNTIME_TYPES = (JSON,)


@strawberry.input
class ScrapedItemErrorInput:
    """Input for reporting scraped item processing failures."""

    item_id: int
    message: str
    is_fatal: bool = False


@strawberry.input
class ScrapedItemCheckoutInput:
    """Optional target for an explicit review checkout."""

    item_id: int | None = None


@strawberry.input
class ScrapedItemActionInput:
    """Identify one item for a review state transition."""

    item_id: int


@strawberry.input
class AgentExtractionInput:
    """Input for staging one agent extraction for review."""

    origin_scraped_item_id: int
    source_page_id: int | None = None
    source_page_url: str = ""
    store_slug: str = ""
    image_report: str = ""
    product: JSON


@strawberry.input
class ReviewedProductCreateInput:
    """Catalog fields explicitly approved for a new product."""

    name: str
    brand_id: int
    weight: int | None = None
    category_id: int | None = None
    ean: str | None = None
    description: str = ""
    packaging: str = "CONTAINER"
    tag_ids: list[int] = strawberry.field(default_factory=list)
    is_published: bool = False


@strawberry.input
class ScrapedItemApprovalInput:
    """Link an approved review to an existing or newly created product."""

    item_id: int
    product_id: int | None = None
    create_product: ReviewedProductCreateInput | None = None
