"""Selectors for public catalog querysets and annotations."""

from decimal import Decimal

from django.conf import settings
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

from offers.models import PriceObservation

from . import units
from .dtos import CatalogProductsFilters
from .models import Active, Product, ProductActive


def _latest_price_observation_subquery() -> QuerySet[PriceObservation]:
    """Return the latest price observations for the outer product.

    Prices live on the merchant offers linked to the product's store listings.
    The ordering is stable so every annotated field comes from the same latest
    observation even when multiple rows share the same timestamp.
    """
    return PriceObservation.objects.filter(
        offer__product_store__product=OuterRef("pk"),
    ).order_by("-observed_at", "-pk")


def catalog_active(slug: str | None = None) -> Active | None:
    """Return the active the catalog ranks by, falling back to the default."""
    wanted = slug or settings.CATALOG_DEFAULT_ACTIVE_SLUG
    return Active.objects.filter(slug=wanted).first()


def _annotate_catalog_base_fields(
    queryset: QuerySet[Product],
    active: Active | None,
) -> QuerySet[Product]:
    """Annotate catalog fields loaded directly from subqueries."""
    latest_prices = _latest_price_observation_subquery()

    fraction = (
        Value(None, output_field=DecimalField(max_digits=12, decimal_places=8))
        if active is None
        else Subquery(
            ProductActive.objects.filter(
                product=OuterRef("pk"),
                active=active.pk,
            ).values("fraction")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=8),
        )
    )

    return queryset.annotate(
        last_price=Subquery(
            latest_prices.values("price")[:1],
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
        external_link=Subquery(
            latest_prices.values("offer__url")[:1],
            output_field=URLField(),
        ),
        fraction=fraction,
    )


def _annotate_catalog_metrics(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate derived catalog metrics from the stored mass fraction.

    Every metric is arithmetic over one dimensionless column, so the same
    expressions serve protein, creatine or caffeine without a per-active branch.
    Masses stay canonical here; the boundary converts them for presentation.
    """
    total_active_safe = NullIf(F("total_active"), Value(0))

    return queryset.annotate(
        total_active=ExpressionWrapper(
            Cast(F("net_mass"), output_field=FloatField())
            * Cast(F("fraction"), output_field=FloatField()),
            output_field=DecimalField(max_digits=16, decimal_places=3),
        ),
        concentration=ExpressionWrapper(
            Cast(F("fraction"), output_field=FloatField()) * 100,
            output_field=DecimalField(max_digits=5, decimal_places=1),
        ),
    ).annotate(
        price_per_active=ExpressionWrapper(
            F("last_price") / Cast(total_active_safe, output_field=FloatField()),
            output_field=DecimalField(max_digits=20, decimal_places=10),
        ),
    )


def public_catalog_products_with_stats(
    active_slug: str | None = None,
) -> QuerySet[Product]:
    """Return public catalog products annotated with catalog-facing metrics.

    The slug is resolved here and nowhere else, so a slug the catalog does not
    know about yields empty metrics instead of silently falling back.
    """
    queryset = Product.objects.select_related("brand", "category").prefetch_related(
        "tags",
    )
    return _annotate_catalog_metrics(
        _annotate_catalog_base_fields(queryset, catalog_active(active_slug)),
    )


SORTABLE_CATALOG_FIELDS = frozenset(
    {
        "price_per_active",
        "last_price",
        "total_active",
        "concentration",
    },
)
DEFAULT_CATALOG_SORT_BY = "price_per_active"
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


def _price_per_canonical_mass(value: float | None) -> float | None:
    """Convert a price per display unit into a price per canonical unit."""
    if value is None:
        return None
    per_display = units.to_canonical(Decimal(1), units.DISPLAY_MASS_UNIT)
    return float(Decimal(str(value)) / per_display)


def _apply_catalog_numeric_filters(
    queryset: QuerySet[Product],
    filters: CatalogProductsFilters,
) -> QuerySet[Product]:
    """Apply numeric range filters to annotated catalog metrics.

    Price bounds arrive in the display unit the catalog presents, so they are
    converted before they meet the canonical annotation.
    """
    numeric_filters = (
        ("last_price__gte", filters.price_min),
        ("last_price__lte", filters.price_max),
        (
            "price_per_active__gte",
            _price_per_canonical_mass(filters.price_per_active_min),
        ),
        (
            "price_per_active__lte",
            _price_per_canonical_mass(filters.price_per_active_max),
        ),
        ("concentration__gte", filters.concentration_min),
        ("concentration__lte", filters.concentration_max),
    )

    for lookup, value in numeric_filters:
        if value is not None:
            queryset = queryset.filter(**{lookup: value})

    return queryset


def _apply_catalog_sorting(
    queryset: QuerySet[Product],
    filters: CatalogProductsFilters,
) -> QuerySet[Product]:
    """Apply stable null-safe ordering to the public catalog."""
    sort_by = (
        filters.sort_by
        if filters.sort_by in SORTABLE_CATALOG_FIELDS
        else DEFAULT_CATALOG_SORT_BY
    )
    sort_dir = (
        filters.sort_dir
        if filters.sort_dir in {"asc", "desc"}
        else DEFAULT_CATALOG_SORT_DIR
    )
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
    queryset = public_catalog_products_with_stats(resolved_filters.active).filter(
        is_published=True,
    )
    queryset = _apply_catalog_search(queryset, resolved_filters)
    queryset = _apply_catalog_brand_filter(queryset, resolved_filters)
    queryset = _apply_catalog_numeric_filters(queryset, resolved_filters)
    return _apply_catalog_sorting(queryset, resolved_filters)
