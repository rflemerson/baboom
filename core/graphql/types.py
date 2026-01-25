import strawberry
from strawberry import auto
from strawberry.django import type as django_type

from baboom.utils import ValidationError
from core.models import (
    Brand,
    Category,
    Flavor,
    Micronutrient,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
    Tag,
)


@django_type(Brand)
class BrandType:
    id: auto
    name: auto
    display_name: auto


@django_type(Store)
class StoreType:
    id: auto
    name: auto
    display_name: auto


@django_type(Category)
class CategoryType:
    id: auto
    name: auto
    description: auto


@django_type(Tag)
class TagType:
    id: auto
    name: auto


@django_type(Flavor)
class FlavorType:
    id: auto
    name: auto


@django_type(Micronutrient)
class MicronutrientType:
    id: auto
    name: auto
    value: auto
    unit: auto


@django_type(NutritionFacts)
class NutritionFactsType:
    id: auto
    description: auto
    serving_size_grams: auto
    energy_kcal: auto
    proteins: auto
    carbohydrates: auto
    total_sugars: auto
    added_sugars: auto
    total_fats: auto
    saturated_fats: auto
    trans_fats: auto
    dietary_fiber: auto
    sodium: auto
    micronutrients: list[MicronutrientType]


@django_type(ProductNutrition)
class ProductNutritionType:
    id: auto
    product: ProductType
    nutrition_facts: NutritionFactsType
    flavors: list[FlavorType]


@django_type(ProductPriceHistory)
class ProductPriceHistoryType:
    id: auto
    price: auto
    stock_status: auto
    collected_at: auto


@django_type(ProductStore)
class ProductStoreType:
    id: auto
    store: StoreType
    external_id: auto
    product_link: auto
    affiliate_link: auto
    price_history: list[ProductPriceHistoryType]


@django_type(Product)
class ProductType:
    id: auto
    name: auto
    weight: auto
    ean: auto
    description: auto
    packaging: auto
    is_published: auto
    created_at: auto
    updated_at: auto
    last_enriched_at: auto
    brand: BrandType
    category: CategoryType | None
    tags: list[TagType]
    store_links: list[ProductStoreType]
    nutrition_profiles: list[ProductNutritionType]


@strawberry.type
class ProductResult:
    product: ProductType | None = None
    errors: list[ValidationError] | None = None
