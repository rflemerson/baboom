from decimal import Decimal
from enum import Enum

import strawberry
from django.db import IntegrityError, transaction
from strawberry import auto

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


@strawberry.input
class ProductInput:
    name: str
    weight: int
    brand_name: str
    category_name: str | None = None
    ean: str | None = None
    description: str | None = ""
    packaging: PackagingEnum = PackagingEnum.CONTAINER
    is_published: bool = False
    tags: list[str] | None = None
    stores: list[ProductStoreInput] | None = None
    nutrition: list[ProductNutritionInput] | None = None


# --- EXCEPTIONS ---


@strawberry.type
class ValidationError:
    field: str
    message: str


@strawberry.type
class ProductResult:
    product: ProductType | None = None
    errors: list[ValidationError] | None = None


# --- MUTATIONS ---


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_product(self, data: ProductInput) -> ProductResult:
        errors: list[ValidationError] = []

        # Validate EAN uniqueness
        if data.ean and Product.objects.filter(ean=data.ean).exists():
            errors.append(ValidationError(field="ean", message="EAN already exists"))

        # Validate unique constraint (brand + name + weight)
        brand_exists = Brand.objects.filter(name=data.brand_name).first()
        if (
            brand_exists
            and Product.objects.filter(
                brand=brand_exists, name=data.name, weight=data.weight
            ).exists()
        ):
            errors.append(
                ValidationError(
                    field="name",
                    message="Product with this brand, name, and weight already exists",
                )
            )

        if errors:
            return ProductResult(errors=errors)

        try:
            with transaction.atomic():
                # 1. Brand
                brand, _ = Brand.objects.get_or_create(
                    name=input.brand_name,
                    defaults={"display_name": input.brand_name},
                )

                # 2. Category
                category = None
                if input.category_name:
                    category = Category.objects.filter(name=input.category_name).first()
                    if not category:
                        category = Category.add_root(name=input.category_name)

                # 3. Product
                product = Product.objects.create(
                    name=input.name,
                    weight=input.weight,
                    brand=brand,
                    category=category,
                    ean=input.ean,
                    description=input.description,
                    packaging=input.packaging.value,
                    is_published=input.is_published,
                )

                # 4. Tags
                if input.tags:
                    tag_objects = []
                    for tag_name in input.tags:
                        tag = Tag.objects.filter(name=tag_name).first()
                        if not tag:
                            tag = Tag.add_root(name=tag_name)
                        tag_objects.append(tag)
                    product.tags.set(tag_objects)

                # 5. Stores & Prices
                if input.stores:
                    for store_input in input.stores:
                        store, _ = Store.objects.get_or_create(
                            name=store_input.store_name,
                            defaults={"display_name": store_input.store_name},
                        )

                        product_store = ProductStore.objects.create(
                            product=product,
                            store=store,
                            external_id=store_input.external_id,
                            product_link=store_input.product_link,
                            affiliate_link=store_input.affiliate_link,
                        )

                        ProductPriceHistory.objects.create(
                            store_product_link=product_store,
                            price=Decimal(str(store_input.price)),
                            stock_status=store_input.stock_status.value,
                        )

                # 6. Nutrition Profiles
                if input.nutrition:
                    for nutr_input in input.nutrition:
                        facts_input = nutr_input.nutrition_facts
                        facts = NutritionFacts.objects.create(
                            description=facts_input.description,
                            serving_size_grams=facts_input.serving_size_grams,
                            energy_kcal=facts_input.energy_kcal,
                            proteins=Decimal(str(facts_input.proteins)),
                            carbohydrates=Decimal(str(facts_input.carbohydrates)),
                            total_sugars=Decimal(str(facts_input.total_sugars)),
                            added_sugars=Decimal(str(facts_input.added_sugars)),
                            total_fats=Decimal(str(facts_input.total_fats)),
                            saturated_fats=Decimal(str(facts_input.saturated_fats)),
                            trans_fats=Decimal(str(facts_input.trans_fats)),
                            dietary_fiber=Decimal(str(facts_input.dietary_fiber)),
                            sodium=facts_input.sodium,
                        )

                        # Bulk create micronutrients
                        if facts_input.micronutrients:
                            micros = [
                                Micronutrient(
                                    nutrition_facts=facts,
                                    name=m.name,
                                    value=Decimal(str(m.value)),
                                    unit=m.unit,
                                )
                                for m in facts_input.micronutrients
                            ]
                            Micronutrient.objects.bulk_create(micros)

                        profile = ProductNutrition.objects.create(
                            product=product, nutrition_facts=facts
                        )

                        if nutr_input.flavor_names:
                            flavor_objects = []
                            for flav_name in nutr_input.flavor_names:
                                flavor, _ = Flavor.objects.get_or_create(name=flav_name)
                                flavor_objects.append(flavor)
                            profile.flavors.set(flavor_objects)

                return ProductResult(product=product)

        except IntegrityError as e:
            return ProductResult(
                errors=[ValidationError(field="unknown", message=str(e))]
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
