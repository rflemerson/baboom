"""Pydantic schemas used by the LLM extraction pipeline."""

from __future__ import annotations

import pydantic
from pydantic import BaseModel, ConfigDict, Field


class MicronutrientItem(BaseModel):
    """Micronutrient data found in a nutrition table."""

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
    micronutrients: list[MicronutrientItem] = Field(default_factory=list)

    @pydantic.field_validator("micronutrients", mode="before")
    @classmethod
    def parse_micros(cls, value: object) -> object:
        """Normalize null-like micronutrient values from LLM output."""
        if value == "null" or value is None:
            return []
        return value


class ExtractedProduct(BaseModel):
    """One product node extracted from a scraped page.

    A page always yields one root product. Kits/combos are represented by
    `children`; each child uses this same contract recursively.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    brand_name: str | None = None
    weight_grams: int | None = None
    packaging: str = "OTHER"
    quantity: int = 1
    category_hierarchy: list[str] = Field(default_factory=list)
    tags_hierarchy: list[list[str]] = Field(default_factory=list)
    nutrition_facts: NutritionFacts | None = None
    flavor_names: list[str] = Field(default_factory=list)
    variant_name: str | None = None
    children: list[ExtractedProduct] = Field(default_factory=list)
