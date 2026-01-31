from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .nutrition import NutritionFacts


class ProductAnalysisResult(BaseModel):
    """
    Unified product analysis result from multimodal LLM.

    Combines fields from Metadata and Nutrition for a single pass extraction.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str | None = Field(
        None, description="Corrected product name if scraper failed"
    )

    # Metadata Fields
    weight_grams: int | None = Field(
        None, description="Product weight in grams extracted from text/image"
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

    # Nutrition & Flavor Fields
    nutrition_facts: NutritionFacts | None = Field(
        None, description="Extracted nutrition table data"
    )
    flavor_names: list[str] = Field(
        default_factory=list,
        description="List of all flavors identified in the product (from text + image)",
    )
