"""Query definitions for the core GraphQL schema."""

from typing import cast

import strawberry
from django.core.paginator import Paginator

from core.filters import ProductFilter
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.models import Category, Product, Tag
from core.selectors import public_catalog_products_with_stats

from .types import (
    CatalogPageInfo,
    CatalogProductsResult,
    CatalogProductType,
    CategoryType,
    ProductType,
    TagType,
)


@strawberry.type
class CoreQuery:
    """GraphQL queries for core module."""

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def catalog_products(
        self,
        search: str | None = None,
        brand: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        price_per_gram_min: float | None = None,
        price_per_gram_max: float | None = None,
        concentration_min: float | None = None,
        concentration_max: float | None = None,
        sort_by: str = "price_per_gram",
        sort_dir: str = "asc",
        page: int = 1,
        per_page: int = 12,
    ) -> CatalogProductsResult:
        """Return the public catalog list from the shared selector pipeline."""
        normalized_per_page = per_page if per_page in {12, 24, 48} else 12
        normalized_page = max(page, 1)

        filter_data: dict[str, str | float] = {
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        }

        optional_filters = {
            "search": search,
            "brand": brand,
            "price_min": price_min,
            "price_max": price_max,
            "price_per_gram_min": price_per_gram_min,
            "price_per_gram_max": price_per_gram_max,
            "concentration_min": concentration_min,
            "concentration_max": concentration_max,
        }
        filter_data.update(
            {
                key: value
                for key, value in optional_filters.items()
                if value not in (None, "")
            },
        )

        queryset = public_catalog_products_with_stats().filter(is_published=True)
        product_filter = ProductFilter(filter_data, queryset=queryset)
        paginator = Paginator(product_filter.qs, normalized_per_page)
        page_obj = paginator.get_page(normalized_page)

        return CatalogProductsResult(
            items=cast("list[CatalogProductType]", list(page_obj.object_list)),
            page_info=CatalogPageInfo(
                current_page=page_obj.number,
                per_page=normalized_per_page,
                total_pages=paginator.num_pages,
                total_count=paginator.count,
                has_previous_page=page_obj.has_previous(),
                has_next_page=page_obj.has_next(),
            ),
        )

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def products(self, limit: int = 50, offset: int = 0) -> list[ProductType]:
        """List products with pagination."""
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
        return cast("list[ProductType]", qs)

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def product(self, product_id: int) -> ProductType | None:
        """Get single product by ID."""
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
        return cast("ProductType | None", obj)

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def categories(self) -> list[CategoryType]:
        """List all categories."""
        return cast("list[CategoryType]", Category.objects.all())

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def tags(self) -> list[TagType]:
        """List all tags."""
        return cast("list[TagType]", Tag.objects.all())
