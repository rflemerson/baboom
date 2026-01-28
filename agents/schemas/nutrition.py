from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class MicronutrientItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    value: float
    unit: str = "mg"


class NutritionFacts(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    serving_size_grams: int = Field(0, description="Serving size in grams")
    energy_kcal: int = Field(0, description="Energy in Kcal")
    energy_kj: int = Field(0, description="Energy in kJ")
    proteins: float = Field(0.0, description="Proteins in grams")
    carbohydrates: float = Field(0.0, description="Carbohydrates in grams")
    total_fats: float = Field(0.0, description="Total fats in grams")
    description: str | None = Field("", description="Facts description")
    total_sugars: float = Field(0.0, description="Total sugars in grams")
    added_sugars: float = Field(0.0, description="Added sugars in grams")
    saturated_fats: float = Field(0.0, description="Saturated fats in grams")
    trans_fats: float = Field(0.0, description="Trans fats in grams")
    dietary_fiber: float = Field(0.0, description="Dietary fiber in grams")
    sodium: int = Field(0, description="Sodium in mg")
    flavor_names: list[str] = Field(
        default_factory=list, description="Flavors identified on this specific label"
    )
    micronutrients: list[MicronutrientItem] | None = None


class ProductNutritionProfile(BaseModel):
    nutrition_facts: NutritionFacts
    flavor_names: list[str] | None = None
