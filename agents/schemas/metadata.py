"""Metadata schemas."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ProductMetadata(BaseModel):
    """Metadata extracted by AI from product name and description."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    weight_grams: int | None = Field(
        None, description="Product weight in grams extracted from text"
    )
    packaging: str = Field(
        "CONTAINER", description="Packaging type: CONTAINER, REFILL, BAR, OTHER"
    )
    category_hierarchy: list[str] = Field(
        default_factory=list,
        description="Hierarchical category path: ['Proteína', 'Whey', 'Concentrado']",
    )
    tags_hierarchy: list[list[str]] = Field(
        default_factory=list,
        description="List of hierarchical tag paths: [['Proteína', 'Whey'], ['Suplemento']]",
    )
