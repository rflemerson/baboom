"""Local extraction validation matching the Django staging contract."""

from pydantic import BaseModel, ConfigDict, Field


class Micronutrient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: float | None = None
    unit: str = ""


class NutritionFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None
    serving_size_grams: float | None = Field(default=None, alias="servingSizeGrams")
    energy_kcal: float | None = Field(default=None, alias="energyKcal")
    proteins: float | None = None
    carbohydrates: float | None = None
    total_sugars: float | None = Field(default=None, alias="totalSugars")
    added_sugars: float | None = Field(default=None, alias="addedSugars")
    total_fats: float | None = Field(default=None, alias="totalFats")
    saturated_fats: float | None = Field(default=None, alias="saturatedFats")
    trans_fats: float | None = Field(default=None, alias="transFats")
    dietary_fiber: float | None = Field(default=None, alias="dietaryFiber")
    sodium: float | None = None
    micronutrients: list[Micronutrient] = Field(default_factory=list)


class ProductDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    brand_name: str | None = Field(default=None, alias="brandName")
    ean: str | None = ""
    weight_grams: int | None = Field(default=None, alias="weightGrams")
    packaging: str | None = ""
    quantity: int | None = None
    description: str | None = ""
    category_hierarchy: list[str] = Field(
        default_factory=list, alias="categoryHierarchy"
    )
    tags_hierarchy: list[list[str]] = Field(default_factory=list, alias="tagsHierarchy")
    flavor_names: list[str] = Field(default_factory=list, alias="flavorNames")
    variant_name: str | None = Field(default=None, alias="variantName")
    nutrition_facts: NutritionFacts | None = Field(default=None, alias="nutritionFacts")
    children: list[ProductDraft] = Field(default_factory=list)
