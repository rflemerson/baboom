"""Selectors for public catalog querysets and annotations."""

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    URLField,
    Value,
)
from django.db.models.functions import Cast, NullIf

from .dtos import CatalogProductsFilters
from .models import NutritionFacts, Product, ProductPriceHistory


def _latest_price_history_subquery() -> QuerySet[ProductPriceHistory]:
    """Return the latest price history rows for the outer product.

    The ordering is stable so every annotated field comes from the same
    latest history row even when multiple rows share the same timestamp.
    """
    return ProductPriceHistory.objects.filter(
        store_product_link__product=OuterRef("pk"),
    ).order_by("-collected_at", "-pk")


def _catalog_nutrition_facts_subquery() -> QuerySet[NutritionFacts]:
    """Return the nutrition facts rows used by the public catalog.

    The public catalog uses the most protein-dense profile for each product.
    Ties fall back to the profile with more protein per serving and then the
    oldest persisted profile for deterministic results.
    """
    serving_size_safe = NullIf(F("serving_size_grams"), Value(0))

    return (
        NutritionFacts.objects.filter(
        product_profiles__product=OuterRef("pk"),
        )
        .annotate(
            protein_concentration=ExpressionWrapper(
                Cast(
                    F("proteins"),
                    output_field=DecimalField(max_digits=10, decimal_places=4),
                )
                / Cast(
                    serving_size_safe,
                    output_field=DecimalField(max_digits=10, decimal_places=4),
                ),
                output_field=DecimalField(max_digits=10, decimal_places=4),
            ),
        )
        .order_by(
            F("protein_concentration").desc(nulls_last=True),
            F("proteins").desc(nulls_last=True),
            "id",
        )
    )


def _annotate_catalog_base_fields(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate catalog fields loaded directly from subqueries."""
    latest_prices = _latest_price_history_subquery()
    nutrition_facts = _catalog_nutrition_facts_subquery()

    return queryset.annotate(
        last_price=Subquery(
            latest_prices.values("price")[:1],
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
        external_link=Subquery(
            latest_prices.values("store_product_link__product_link")[:1],
            output_field=URLField(),
        ),
        protein_per_serving=Subquery(
            nutrition_facts.values("proteins")[:1],
            output_field=DecimalField(max_digits=5, decimal_places=1),
        ),
        serving_size_grams_value=Subquery(
            nutrition_facts.values("serving_size_grams")[:1],
            output_field=DecimalField(max_digits=5, decimal_places=1),
        ),
    )


def _annotate_catalog_metrics(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate derived catalog metrics from the base catalog fields."""
    serving_size_safe = NullIf(F("serving_size_grams_value"), Value(0))
    total_protein_safe = NullIf(F("total_protein"), Value(0))

    return (
        queryset.annotate(
            total_protein=ExpressionWrapper(
                (
                    F("weight")
                    * Cast(F("protein_per_serving"), output_field=FloatField())
                )
                / Cast(serving_size_safe, output_field=FloatField()),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            concentration=ExpressionWrapper(
                (
                    Cast(F("protein_per_serving"), output_field=FloatField())
                    / Cast(serving_size_safe, output_field=FloatField())
                )
                * 100,
                output_field=DecimalField(max_digits=5, decimal_places=1),
            ),
        )
        .annotate(
            price_per_protein_gram=ExpressionWrapper(
                F("last_price") / Cast(total_protein_safe, output_field=FloatField()),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
    )


def public_catalog_products_with_stats() -> QuerySet[Product]:
    """Return public catalog products annotated with catalog-facing metrics."""
    queryset = Product.objects.select_related("brand", "category").prefetch_related(
        "tags",
    )
    return _annotate_catalog_metrics(_annotate_catalog_base_fields(queryset))

SORTABLE_CATALOG_FIELDS = frozenset(
    {
        "price_per_protein_gram",
        "last_price",
        "total_protein",
        "concentration",
    },
)
DEFAULT_CATALOG_SORT_BY = "price_per_protein_gram"
DEFAULT_CATALOG_SORT_DIR = "asc"


def _apply_catalog_search(
    queryset: QuerySet[Product],
    filters: CatalogProductsFilters,
) -> QuerySet[Product]:
    """Apply the public catalog full-text-ish search fields."""
    if not filters.search:
        return queryset

    return queryset.filter(
        Q(name__icontains=filters.search)
        | Q(brand__name__icontains=filters.search)
        | Q(category__name__icontains=filters.search)
        | Q(tags__name__icontains=filters.search)
        | Q(nutrition_profiles__flavors__name__icontains=filters.search)
        | Q(description__icontains=filters.search),
    ).distinct()


def _apply_catalog_brand_filter(
    queryset: QuerySet[Product],
    filters: CatalogProductsFilters,
) -> QuerySet[Product]:
    """Apply brand filtering when a brand query is present."""
    if not filters.brand:
        return queryset
    return queryset.filter(brand__name__icontains=filters.brand)


def _apply_catalog_numeric_filters(
    queryset: QuerySet[Product],
    filters: CatalogProductsFilters,
) -> QuerySet[Product]:
    """Apply numeric range filters to annotated catalog metrics."""
    numeric_filters = (
        ("last_price__gte", filters.price_min),
        ("last_price__lte", filters.price_max),
        ("price_per_protein_gram__gte", filters.price_per_protein_gram_min),
        ("price_per_protein_gram__lte", filters.price_per_protein_gram_max),
        ("concentration__gte", filters.concentration_min),
        ("concentration__lte", filters.concentration_max),
    )

    for lookup, value in numeric_filters:
        if value is not None:
            queryset = queryset.filter(**{lookup: value})

    return queryset


def _resolve_catalog_sort_by(filters: CatalogProductsFilters) -> str:
    """Return a supported catalog sort field."""
    if filters.sort_by in SORTABLE_CATALOG_FIELDS:
        return filters.sort_by
    return DEFAULT_CATALOG_SORT_BY


def _resolve_catalog_sort_dir(filters: CatalogProductsFilters) -> str:
    """Return a supported catalog sort direction."""
    if filters.sort_dir in {"asc", "desc"}:
        return filters.sort_dir
    return DEFAULT_CATALOG_SORT_DIR


def _apply_catalog_sorting(
    queryset: QuerySet[Product],
    filters: CatalogProductsFilters,
) -> QuerySet[Product]:
    """Apply stable null-safe ordering to the public catalog."""
    sort_by = _resolve_catalog_sort_by(filters)
    sort_dir = _resolve_catalog_sort_dir(filters)
    ordering = F(sort_by)
    stable_fallback = ["brand__name", "name", "pk"]

    if sort_dir == "desc":
        return queryset.order_by(ordering.desc(nulls_last=True), *stable_fallback)
    return queryset.order_by(ordering.asc(nulls_last=True), *stable_fallback)


def public_catalog_products(
    filters: CatalogProductsFilters | None = None,
) -> QuerySet[Product]:
    """Return the public catalog queryset with filters and sorting applied."""
    resolved_filters = filters or CatalogProductsFilters()
    queryset = public_catalog_products_with_stats().filter(is_published=True)
    queryset = _apply_catalog_search(queryset, resolved_filters)
    queryset = _apply_catalog_brand_filter(queryset, resolved_filters)
    queryset = _apply_catalog_numeric_filters(queryset, resolved_filters)
    return _apply_catalog_sorting(queryset, resolved_filters)
