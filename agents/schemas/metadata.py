from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ProductMetadata(BaseModel):
    """
    Metadata extracted by AI from product name and description.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    weight_grams: int | None = Field(
        None, description="Product weight in grams extracted from text"
    )
    packaging: str = Field(
        "CONTAINER", description="Packaging type: CONTAINER, REFILL, BAR, OTHER"
    )
    category: str = Field(
        "General", description="Product category: Whey Protein, Creatina, BCAA, etc."
    )
    tags: list[str] = Field(
        default_factory=list, description="Relevant tags based on product description"
    )
