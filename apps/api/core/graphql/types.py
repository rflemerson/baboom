from __future__ import annotations

from decimal import Decimal

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
    """Brand GraphQL type."""

    id: auto
    name: auto
    display_name: auto


@django_type(Store)
class StoreType:
    """Store GraphQL type."""

    id: auto
    name: auto
    display_name: auto


@django_type(Category)
class CategoryType:
    """Category GraphQL type."""

    id: auto
    name: auto
    description: auto


@django_type(Tag)
class TagType:
    """Tag GraphQL type."""

    id: auto
    name: auto


@django_type(Flavor)
class FlavorType:
    """Flavor GraphQL type."""

    id: auto
    name: auto


@django_type(Micronutrient)
class MicronutrientType:
    """Micronutrient GraphQL type."""

    id: auto
    name: auto
    value: auto
    unit: auto


@django_type(NutritionFacts)
class NutritionFactsType:
    """Nutrition Facts GraphQL type."""

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
    """Product Nutrition Profile GraphQL type."""

    id: auto
    product: ProductType
    nutrition_facts: NutritionFactsType
    flavors: list[FlavorType]


@django_type(ProductPriceHistory)
class ProductPriceHistoryType:
    """Product Price History GraphQL type."""

    id: auto
    price: auto
    stock_status: auto
    collected_at: auto


@django_type(ProductStore)
class ProductStoreType:
    """Product Store Link GraphQL type."""

    id: auto
    store: StoreType
    external_id: auto
    product_link: auto
    affiliate_link: auto
    price_history: list[ProductPriceHistoryType]


@django_type(Product)
class ProductType:
    """Product GraphQL type."""

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
    """Result type for Product mutations."""

    product: ProductType | None = None
    errors: list[ValidationError] | None = None


@strawberry.type
class CatalogProductType:
    """Product list item tailored for the public catalog."""

    id: int
    name: str
    weight: int
    packaging: str
    is_published: bool
    brand: BrandType
    category: CategoryType | None
    last_price: Decimal | None = None
    price_per_gram: Decimal | None = None
    concentration: Decimal | None = None
    total_protein: Decimal | None = None
    external_link: str | None = None

    @strawberry.field
    def packaging_display(self) -> str:
        """Return the human-readable packaging label."""
        return self.get_packaging_display()

    @strawberry.field
    def tags(self) -> list[TagType]:
        """Return tags as a concrete list for GraphQL serialization."""
        return list(self.tags.all())


@strawberry.type
class CatalogPageInfo:
    """Pagination metadata for the public catalog."""

    current_page: int
    per_page: int
    total_pages: int
    total_count: int
    has_previous_page: bool
    has_next_page: bool


@strawberry.type
class CatalogProductsResult:
    """Catalog listing payload for the public frontend."""

    items: list[CatalogProductType]
    page_info: CatalogPageInfo
