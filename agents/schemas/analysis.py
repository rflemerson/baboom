"""Schemas for LLM analysis results."""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from .nutrition import NutritionFacts


class ComboComponent(BaseModel):
    """A component product detected inside a combo/kit."""

    name: str = Field(..., description="Name of the component product e.g. 'Whey 900g'")
    quantity: int = Field(1, description="Quantity of this component")
    weight_hint: int | None = Field(
        None, description="Estimated weight of this component in grams if available"
    )
    packaging_hint: str | None = Field(
        None, description="Packaging type (REFILL/CONTAINER) if explicitly mentioned"
    )


class ProductAnalysisResult(BaseModel):
    """
    Unified product analysis result from multimodal LLM.

    Combines fields from Metadata and Nutrition for a single pass extraction.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str | None = Field(
        None, description="Corrected product name if scraper failed"
    )

    is_combo: bool = Field(
        False, description="True if this product is a kit/bundle/combo of items"
    )
    components: list[ComboComponent] = Field(
        default_factory=list,
        description="List of items in the combo (if is_combo=True)",
    )

    # Metadata Fields
    weight_grams: int | None = Field(
        None, description="Product weight in grams extracted from text/image"
    )
    packaging: str = Field(
        "CONTAINER", description="Packaging type: CONTAINER, REFILL, BAR, OTHER"
    )
    # Classification
    nutrient_claims: list[str] = Field(
        default_factory=list,
        description="List of slugs for significant nutrient sources (e.g. ['protein', 'creatine', 'vitamin-c', 'omega-3'])",
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
