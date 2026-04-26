"""Typed DTOs shared by core services and ingestion workflows."""

from pydantic import BaseModel

from .models import Product


class ComboComponentInput(BaseModel):
    """DTO for a combo component input."""

    name: str
    weight: int | None = None
    brand_name: str | None = None
    category_name: str | list[str] | None = None
    ean: str | None = None
    description: str | None = ""
    packaging: str = Product.Packaging.CONTAINER
    tags: list[str] | list[list[str]] | None = None
    stores: list[StoreListingPayload] | None = None
    nutrition: list[ProductNutritionPayload] | None = None
    external_id: str | None = None
    quantity: int = 1


class MicronutrientPayload(BaseModel):
    """DTO for a micronutrient entry within nutrition data."""

    name: str
    value: float
    unit: str = "mg"


class NutritionFactsPayload(BaseModel):
    """DTO for a nutrition facts payload."""

    serving_size_grams: float
    energy_kcal: int
    proteins: float
    carbohydrates: float
    total_fats: float
    description: str | None = ""
    total_sugars: float = 0.0
    added_sugars: float = 0.0
    saturated_fats: float = 0.0
    trans_fats: float = 0.0
    dietary_fiber: float = 0.0
    sodium: float = 0.0
    micronutrients: list[MicronutrientPayload] | None = None


class ProductNutritionPayload(BaseModel):
    """DTO for nutrition profile data linked to a product."""

    nutrition_facts: NutritionFactsPayload
    flavor_names: list[str] | None = None


class StoreListingPayload(BaseModel):
    """DTO for a store listing attached to a product."""

    store_name: str
    product_link: str
    price: float
    external_id: str | None = ""
    affiliate_link: str | None = None
    stock_status: str = "A"


class ProductCreateInput(BaseModel):
    """DTO for product creation service."""

    name: str
    weight: int | None = None
    brand_name: str
    category_name: str | list[str] | None = None
    ean: str | None = None
    description: str | None = ""
    origin_scraped_item_id: int | None = None
    packaging: str = Product.Packaging.CONTAINER
    is_published: bool = False
    tags: list[str] | list[list[str]] | None = None
    stores: list[StoreListingPayload] | None = None
    nutrition: list[ProductNutritionPayload] | None = None

    is_combo: bool = False
    components: list[ComboComponentInput] | None = None


class ProductMetadataUpdateInput(BaseModel):
    """DTO for metadata-only product updates."""

    name: str | None = None
    description: str | None = None
    category_name: str | list[str] | None = None
    packaging: str | None = None
    is_published: bool | None = None
    tags: list[str] | list[list[str]] | None = None


class CatalogProductsFilters(BaseModel):
    """DTO for public catalog filtering and sorting."""

    search: str | None = None
    brand: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    price_per_protein_gram_min: float | None = None
    price_per_protein_gram_max: float | None = None
    concentration_min: float | None = None
    concentration_max: float | None = None
    sort_by: str = "price_per_protein_gram"
    sort_dir: str = "asc"


ComboComponentInput.model_rebuild()
