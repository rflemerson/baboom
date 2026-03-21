"""Pydantic schemas for nutrition data."""

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
    def parse_micros(cls, v: object) -> object:
        """Handle 'null' string inputs from LLM."""
        if v == "null" or v is None:
            return []
        return v


class ProductNutritionProfile(BaseModel):
    """Complete nutritional profile of a product."""

    nutrition_facts: NutritionFacts
    flavor_names: list[str] | None = None
