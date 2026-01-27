from pydantic import BaseModel, Field

from .nutrition import ProductNutritionProfile


class RawScrapedData(BaseModel):
    """
    Data extracted directly from the HTML without AI enrichment.
    """

    name: str
    brand_name: str
    ean: str | None = None
    description: str | None = None
    image_url: str | None = None
    price: float | None = None
    stock_status: str | None = "A"


class ScrapedProductData(BaseModel):
    """
    Consolidated payload to be returned by variables for the GraphQL Mutation
    """

    name: str
    brand_name: str
    weight: int = Field(..., description="Weight in grams")
    category_name: str | None = Field(None, description="Category name (legacy)")
    category_path: list[str] = Field(
        default_factory=list, description="Hierarchical category path"
    )
    ean: str | None = None
    description: str | None = None
    image_url: str | None = (
        None  # Note: Keep for reference, but check if API accepts it
    )
    nutrition: list[ProductNutritionProfile] | None = None
    tags: list[str] = Field(default_factory=list, description="List of tags (legacy)")
    tag_paths: list[list[str]] = Field(
        default_factory=list, description="List of hierarchical tag paths"
    )
    packaging: str = Field(
        "CONTAINER", description="Packaging type: CONTAINER, REFILL, BAR, OTHER"
    )
    origin_scraped_item_id: int
