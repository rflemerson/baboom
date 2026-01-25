import strawberry

from .enums import PackagingEnum, StockStatusEnum


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
        default=None, description="Category name"
    )
    ean: str | None = strawberry.field(default=None, description="Barcode")
    description: str | None = strawberry.field(
        default="", description="Marketing description"
    )
    packaging: PackagingEnum = strawberry.field(
        default=PackagingEnum.CONTAINER, description="Packaging type"
    )
    is_published: bool = strawberry.field(
        default=False, description="Visible on public site"
    )
    tags: list[str] | None = strawberry.field(default=None, description="Tag names")
    stores: list[ProductStoreInput] | None = strawberry.field(
        default=None, description="Store links"
    )
    nutrition: list[ProductNutritionInput] | None = strawberry.field(
        default=None, description="Nutrition profiles"
    )


@strawberry.input(description="Input for updating product content only")
class ProductContentUpdateInput:
    name: str | None = None
    description: str | None = None
    category_name: str | None = None
    packaging: PackagingEnum | None = None
    tags: list[str] | None = None
