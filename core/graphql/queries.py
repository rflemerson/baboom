from typing import cast

import strawberry

from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.models import Category, Product, Tag

from .types import CategoryType, ProductType, TagType


@strawberry.type
class CoreQuery:
    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def products(self, limit: int = 50, offset: int = 0) -> list[ProductType]:
        qs = (
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
        return cast(list[ProductType], qs)

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def product(self, product_id: int) -> ProductType | None:
        obj = (
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
        return cast(ProductType | None, obj)

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def categories(self) -> list[CategoryType]:
        return cast(list[CategoryType], Category.objects.all())

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def tags(self) -> list[TagType]:
        return cast(list[TagType], Tag.objects.all())
