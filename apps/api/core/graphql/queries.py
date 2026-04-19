"""Query definitions for the core GraphQL schema."""

from typing import TYPE_CHECKING

import strawberry
from django.core.paginator import Paginator

from core.dtos import CatalogProductsFilters as CatalogProductsFiltersDTO
from core.graphql.permissions import IsAuthenticatedWithAPIKey
from core.models import Category, Product, Tag
from core.selectors import public_catalog_products

from .inputs import CatalogProductsFiltersInput
from .types import (
    CatalogPageInfo,
    CatalogProductsResult,
    CategoryType,
    ProductType,
    TagType,
)

MAX_PRODUCTS_LIMIT = 100

if TYPE_CHECKING:
    from django.db.models import QuerySet


def _product_detail_queryset() -> QuerySet[Product]:
    """Return the shared queryset used by product list and detail queries."""
    return Product.objects.select_related("brand", "category").prefetch_related(
        "tags",
        "store_links__store",
        "store_links__price_history",
        "nutrition_profiles__nutrition_facts__micronutrients",
        "nutrition_profiles__flavors",
    )


@strawberry.type
class CoreQuery:
    """GraphQL queries for core module."""

    @strawberry.field
    def catalog_products(
        self,
        filters: CatalogProductsFiltersInput | None = None,
    ) -> CatalogProductsResult:
        """Return the public catalog list from the shared selector pipeline."""
        resolved_filters = filters or CatalogProductsFiltersInput()
        normalized_per_page = (
            resolved_filters.per_page
            if resolved_filters.per_page in {12, 24, 48}
            else 12
        )
        normalized_page = max(resolved_filters.page, 1)

        query_filters = CatalogProductsFiltersDTO(
            search=resolved_filters.search,
            brand=resolved_filters.brand,
            price_min=resolved_filters.price_min,
            price_max=resolved_filters.price_max,
            price_per_protein_gram_min=resolved_filters.price_per_protein_gram_min,
            price_per_protein_gram_max=resolved_filters.price_per_protein_gram_max,
            concentration_min=resolved_filters.concentration_min,
            concentration_max=resolved_filters.concentration_max,
            sort_by=resolved_filters.sort_by,
            sort_dir=resolved_filters.sort_dir,
        )

        queryset = public_catalog_products(query_filters)
        paginator = Paginator(queryset, normalized_per_page)
        page_obj = paginator.get_page(normalized_page)

        return CatalogProductsResult(
            items=list(page_obj.object_list),
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
    def products(
        self,
        limit: int = MAX_PRODUCTS_LIMIT // 2,
        offset: int = 0,
    ) -> list[ProductType]:
        """List products with pagination."""
        normalized_limit = min(max(limit, 1), MAX_PRODUCTS_LIMIT)
        normalized_offset = max(offset, 0)
        return _product_detail_queryset().all()[
            normalized_offset : normalized_offset + normalized_limit
        ]

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def product(self, product_id: int) -> ProductType | None:
        """Get single product by ID."""
        return _product_detail_queryset().filter(id=product_id).first()

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def categories(self) -> list[CategoryType]:
        """List all categories."""
        return Category.objects.all()

    @strawberry.field(permission_classes=[IsAuthenticatedWithAPIKey])
    def tags(self) -> list[TagType]:
        """List all tags."""
        return Tag.objects.all()
