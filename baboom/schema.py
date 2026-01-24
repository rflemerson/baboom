from __future__ import annotations

from enum import Enum

import strawberry
from strawberry import auto

from baboom.utils import ValidationError, format_graphql_errors
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

# --- ENUMS ---


@strawberry.enum
class PackagingEnum(Enum):
    REFILL = "REFILL"
    CONTAINER = "CONTAINER"
    BAR = "BAR"
    OTHER = "OTHER"


@strawberry.enum
class StockStatusEnum(Enum):
    AVAILABLE = "A"
    LAST_UNITS = "L"
    OUT_OF_STOCK = "O"


# --- TYPES ---


@strawberry.django.type(Brand)
class BrandType:
    id: auto
    name: auto
    display_name: auto


@strawberry.django.type(Store)
class StoreType:
    id: auto
    name: auto
    display_name: auto


@strawberry.django.type(Category)
class CategoryType:
    id: auto
    name: auto
    description: auto


@strawberry.django.type(Tag)
class TagType:
    id: auto
    name: auto


@strawberry.django.type(Flavor)
class FlavorType:
    id: auto
    name: auto


@strawberry.django.type(Micronutrient)
class MicronutrientType:
    id: auto
    name: auto
    value: auto
    unit: auto


@strawberry.django.type(NutritionFacts)
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


@strawberry.django.type(ProductNutrition)
class ProductNutritionType:
    id: auto
    product: ProductType
    nutrition_facts: NutritionFactsType
    flavors: list[FlavorType]


@strawberry.django.type(ProductPriceHistory)
class ProductPriceHistoryType:
    id: auto
    price: auto
    stock_status: auto
    collected_at: auto


@strawberry.django.type(ProductStore)
class ProductStoreType:
    id: auto
    store: StoreType
    external_id: auto
    product_link: auto
    affiliate_link: auto
    price_history: list[ProductPriceHistoryType]


@strawberry.django.type(Product)
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


# --- INPUTS ---


@strawberry.input
class MicronutrientInput:
    name: str
    value: float
    unit: str = "mg"


@strawberry.input
class NutritionFactsInput:
    serving_size_grams: int
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
    sodium: int = 0
    micronutrients: list[MicronutrientInput] | None = None


@strawberry.input
class ProductNutritionInput:
    nutrition_facts: NutritionFactsInput
    flavor_names: list[str] | None = None


@strawberry.input
class ProductStoreInput:
    store_name: str
    product_link: str
    price: float
    external_id: str | None = ""
    affiliate_link: str | None = None
    stock_status: StockStatusEnum = StockStatusEnum.AVAILABLE


@strawberry.input(description="Input for creating a new product with all related data")
class ProductInput:
    name: str = strawberry.field(description="Product display name")
    weight: int = strawberry.field(description="Weight in grams")
    brand_name: str = strawberry.field(
        description="Brand name (auto-created if not exists)"
    )
    category_name: str | None = strawberry.field(
        default=None, description="Category name (auto-created as root node)"
    )
    ean: str | None = strawberry.field(
        default=None, description="Barcode (must be unique)"
    )
    description: str | None = strawberry.field(
        default="", description="Marketing description"
    )
    packaging: PackagingEnum = strawberry.field(
        default=PackagingEnum.CONTAINER, description="Packaging type"
    )
    is_published: bool = strawberry.field(
        default=False, description="Visible on public site"
    )
    tags: list[str] | None = strawberry.field(
        default=None, description="Tag names (auto-created)"
    )
    stores: list[ProductStoreInput] | None = strawberry.field(
        default=None, description="Store links with prices"
    )
    nutrition: list[ProductNutritionInput] | None = strawberry.field(
        default=None, description="Nutrition profiles per flavor"
    )


# --- EXCEPTIONS ---


# --- EXCEPTIONS ---


@strawberry.type
class ProductResult:
    product: ProductType | None = None
    errors: list[ValidationError] | None = None


# --- MUTATIONS ---


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_product(self, data: ProductInput) -> ProductResult:
        from django.core.exceptions import ValidationError as DjangoValidationError

        from core.services import product_create

        # Convert inputs for service
        stores_data = []
        if data.stores:
            for s in data.stores:
                stores_data.append(
                    {
                        "store_name": s.store_name,
                        "product_link": s.product_link,
                        "price": s.price,
                        "external_id": s.external_id,
                        "affiliate_link": s.affiliate_link,
                        "stock_status": s.stock_status.value,
                    }
                )

        nutrition_data = []
        if data.nutrition:
            for n in data.nutrition:
                facts = n.nutrition_facts
                micronutrients_data = []
                if facts.micronutrients:
                    for m in facts.micronutrients:
                        micronutrients_data.append(
                            {
                                "name": m.name,
                                "value": m.value,
                                "unit": m.unit,
                            }
                        )

                nutrition_data.append(
                    {
                        "flavor_names": n.flavor_names,
                        "nutrition_facts": {
                            "description": facts.description,
                            "serving_size_grams": facts.serving_size_grams,
                            "energy_kcal": facts.energy_kcal,
                            "proteins": facts.proteins,
                            "carbohydrates": facts.carbohydrates,
                            "total_sugars": facts.total_sugars,
                            "added_sugars": facts.added_sugars,
                            "total_fats": facts.total_fats,
                            "saturated_fats": facts.saturated_fats,
                            "trans_fats": facts.trans_fats,
                            "dietary_fiber": facts.dietary_fiber,
                            "sodium": facts.sodium,
                            "micronutrients": micronutrients_data,
                        },
                    }
                )

        try:
            product = product_create(
                name=data.name,
                weight=data.weight,
                brand_name=data.brand_name,
                category_name=data.category_name,
                ean=data.ean,
                description=data.description,
                packaging=data.packaging.value,
                is_published=data.is_published,
                tags=data.tags,
                stores=stores_data,
                nutrition=nutrition_data,
            )
            return ProductResult(product=product)

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))

    @strawberry.mutation(
        description="Update product content/metadata only. Does NOT touch prices."
    )
    def update_product_content(
        self, product_id: int, data: ProductContentUpdateInput
    ) -> ProductResult:
        from django.core.exceptions import ValidationError as DjangoValidationError

        from core.services import product_update_content

        """
        Updates product metadata (description, category, tags) without modifying price data.
        Mutation used for product enrichment.
        Prices are managed by scrapers; content is managed by enrichment.
        """
        product = Product.objects.filter(id=product_id).first()

        if not product:
            return ProductResult(
                errors=[
                    ValidationError(field="product_id", message="Product not found")
                ]
            )

        try:
            updated_product = product_update_content(
                product=product,
                name=data.name,
                description=data.description,
                category_name=data.category_name,
                packaging=data.packaging.value if data.packaging else None,
                tags=data.tags,
            )
            return ProductResult(product=updated_product)

        except DjangoValidationError as e:
            return ProductResult(errors=format_graphql_errors(e))


@strawberry.input(
    description="Input for updating product content only (no price changes)"
)
class ProductContentUpdateInput:
    name: str | None = strawberry.field(
        default=None, description="New product name (optional)"
    )
    description: str | None = strawberry.field(
        default=None, description="New description (optional)"
    )
    category_name: str | None = strawberry.field(
        default=None, description="New category name (optional, empty string to clear)"
    )
    packaging: PackagingEnum | None = strawberry.field(
        default=None, description="New packaging type (optional)"
    )
    tags: list[str] | None = strawberry.field(
        default=None, description="Replace all tags with these (optional)"
    )


# --- QUERIES ---


@strawberry.type
class Query:
    @strawberry.field
    def products(self, limit: int = 50, offset: int = 0) -> list[ProductType]:
        return (
            Product.objects.select_related("brand", "category")
            .prefetch_related(
                "tags",
                "store_links__store",
                "store_links__price_history",
                "nutrition_profiles__nutrition_facts__micronutrients",
                "nutrition_profiles__flavors",
            )
            .all()[offset : offset + limit]
        )

    @strawberry.field
    def product(self, product_id: int) -> ProductType | None:
        return (
            Product.objects.select_related("brand", "category")
            .prefetch_related(
                "tags",
                "store_links__store",
                "store_links__price_history",
                "nutrition_profiles__nutrition_facts__micronutrients",
                "nutrition_profiles__flavors",
            )
            .filter(id=product_id)
            .first()
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
