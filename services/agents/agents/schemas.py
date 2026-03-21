"""Pydantic schemas used by the LLM extraction pipeline."""

import pydantic
from pydantic import BaseModel, ConfigDict, Field


class MicronutrientItem(BaseModel):
    """Micronutrient (vitamin/mineral) data."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    value: float
    unit: str = "mg"


class NutritionFacts(BaseModel):
    """Structured nutrition table data."""

    model_config = ConfigDict(populate_by_name=True)

    serving_size_grams: float | None = Field(None, description="Serving size in grams")
    energy_kcal: int | None = Field(None, description="Energy in Kcal")
    proteins: float | None = Field(None, description="Proteins in grams")
    carbohydrates: float | None = Field(None, description="Carbohydrates in grams")
    total_fats: float | None = Field(None, description="Total fats in grams")
    description: str | None = Field(None, description="Facts description")
    total_sugars: float | None = Field(None, description="Total sugars in grams")
    added_sugars: float | None = Field(None, description="Added sugars in grams")
    saturated_fats: float | None = Field(None, description="Saturated fats in grams")
    trans_fats: float | None = Field(None, description="Trans fats in grams")
    dietary_fiber: float | None = Field(None, description="Dietary fiber in grams")
    sodium: float | None = Field(None, description="Sodium in mg")
    flavor_names: list[str] = Field(
        default_factory=list,
        description="Flavors identified on this specific label",
    )
    micronutrients: list[MicronutrientItem] | None = None

    @pydantic.field_validator("micronutrients", mode="before")
    @classmethod
    def parse_micros(cls, value: object) -> object:
        """Handle 'null' string inputs from LLM."""
        if value == "null" or value is None:
            return []
        return value


class ComboComponent(BaseModel):
    """A component product detected inside a combo/kit."""

    name: str = Field(..., description="Name of the component product e.g. 'Whey 900g'")
    ean: str | None = Field(
        None,
        description="EAN/GTIN of the component when explicitly present",
    )
    external_id: str | None = Field(
        None,
        description="Store-specific external identifier when explicitly present",
    )
    quantity: int = Field(1, description="Quantity of this component")


class ProductAnalysisResult(BaseModel):
    """Unified product analysis result from multimodal LLM."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(
        None,
        description="Corrected product name if scraper failed",
    )
    is_combo: bool = Field(
        default=False,
        description="True if this product is a kit/bundle/combo of items",
    )
    components: list[ComboComponent] = Field(
        default_factory=list,
        description="List of items in the combo (if is_combo=True)",
    )
    weight_grams: int | None = Field(
        None,
        description="Product weight in grams extracted from text/image",
    )
    packaging: str = Field(
        "CONTAINER",
        description="Packaging type: CONTAINER, REFILL, BAR, OTHER",
    )
    category_hierarchy: list[str] = Field(
        default_factory=list,
        description="Hierarchical category path",
    )
    tags_hierarchy: list[list[str]] = Field(
        default_factory=list,
        description="List of hierarchical tag paths",
    )
    nutrition_facts: NutritionFacts | None = Field(
        None,
        description="Extracted nutrition table data",
    )
    flavor_names: list[str] = Field(
        default_factory=list,
        description="List of all flavors identified in the product",
    )
    variant_name: str | None = Field(
        None,
        description="Name of the specific variation",
    )
    is_variant: bool = Field(
        default=False,
        description="True if this is a variation of a main product",
    )
    parent_name: str | None = Field(
        None,
        description="Name of the parent product if this is a variant",
    )


class ProductAnalysisList(BaseModel):
    """List of analyzed products found on the page."""

    items: list[ProductAnalysisResult]
