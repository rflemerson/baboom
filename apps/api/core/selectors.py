"""Selectors for public catalog querysets and annotations."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    JSONField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    URLField,
    Value,
)
from django.db.models.functions import Cast, Coalesce, NullIf

from commerce.models import Market
from offers.models import Offer, StockStatus

from .dtos import CatalogProductsFilters
from .models import Active, ComboActive, Product, ProductActive, ProductNutrition

# A price source returns, for the outer product, its priced offers cheapest
# first, each with ``amount``, ``url`` and ``payment_method``. The catalog does
# not know which pricing policy produced them.
PriceSource = Callable[[], QuerySet]


def current_prices(country: str, currency: str) -> PriceSource:
    """Return each offer's last read price, for markets not switched to pricing.

    Temporary: serves the catalog until ``PRICING_PROJECTION_COUNTRIES`` names
    the market, and goes with that setting once every market reads
    projections. A store of another known market never competes.
    """
    foreign = Market.objects.exclude(country=country, currency_id=currency).values(
        "namespace",
    )

    def source() -> QuerySet:
        return (
            Offer.objects.filter(
                product_store__product=OuterRef("pk"),
                current_price__isnull=False,
                delisted_at__isnull=True,
                current_stock_status__in=StockStatus.purchasable(),
            )
            .exclude(store_slug__in=foreign)
            .annotate(
                amount=F("current_price"),
                comparison_amount=F("current_price"),
                pricing_details=Value({}, output_field=JSONField()),
                payment_method=Value(""),
                offer_id=F("pk"),
                expires_at=Value(None, output_field=DateTimeField()),
                link_fixes=Coalesce(
                    F("seller_account__is_channel_owner"),
                    Value(value=True),
                ),
            )
            .order_by("current_price", "pk")
        )

    return source


def catalog_active(slug: str | None = None) -> Active | None:
    """Return the active the catalog ranks by, falling back to the default."""
    wanted = slug or settings.CATALOG_DEFAULT_ACTIVE_SLUG
    return Active.objects.filter(slug=wanted).first()


def _annotate_catalog_base_fields(
    queryset: QuerySet[Product],
    active: Active | None,
    price_source: PriceSource,
) -> QuerySet[Product]:
    """Annotate catalog fields loaded directly from subqueries."""
    cheapest = price_source()

    fraction = (
        Value(None, output_field=DecimalField(max_digits=12, decimal_places=8))
        if active is None
        else Subquery(
            ProductActive.objects.filter(
                nutrition_profile=OuterRef("nutrition_profile_id"),
                active=active.pk,
            ).values("fraction")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=8),
        )
    )

    combo_total_active = (
        Value(None, output_field=DecimalField(max_digits=16, decimal_places=3))
        if active is None
        else Subquery(
            ComboActive.objects.filter(
                combo=OuterRef("pk"),
                active=active.pk,
            ).values("total_mass")[:1],
            output_field=DecimalField(max_digits=16, decimal_places=3),
        )
    )

    return queryset.annotate(
        # Projections keep the source's precision; the API rounds to the
        # currency's own minor unit when it serializes.
        price=Subquery(
            cheapest.values("amount")[:1],
            output_field=DecimalField(max_digits=19, decimal_places=6),
        ),
        comparison_price=Subquery(cheapest.values("comparison_amount")[:1]),
        pricing_details=Subquery(cheapest.values("pricing_details")[:1]),
        external_link=Subquery(
            cheapest.values("url")[:1],
            output_field=URLField(),
        ),
        payment_method=Subquery(
            cheapest.values("payment_method")[:1],
            output_field=CharField(),
        ),
        price_offer_id=Subquery(
            cheapest.values("offer_id")[:1],
            output_field=IntegerField(),
        ),
        price_expires_at=Subquery(
            cheapest.values("expires_at")[:1],
            output_field=DateTimeField(),
        ),
        link_selects_seller=Subquery(
            cheapest.values("link_fixes")[:1],
            output_field=BooleanField(),
        ),
        fraction=fraction,
        combo_total_active=combo_total_active,
    )


def _annotate_catalog_metrics(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate derived catalog metrics from the stored mass fraction.

    Every metric is arithmetic over one dimensionless column, so the same
    expressions serve protein, creatine or caffeine without a per-active branch.
    Masses are in grams, as stored and as published.
    """
    total_active_safe = NullIf(F("total_active"), Value(0))

    # A simple product's total comes from its label; a combo has no label and
    # carries the total summed from its components instead.
    return queryset.annotate(
        total_active=ExpressionWrapper(
            Coalesce(
                Cast(F("net_mass"), output_field=FloatField())
                * Cast(F("fraction"), output_field=FloatField()),
                Cast(F("combo_total_active"), output_field=FloatField()),
                output_field=FloatField(),
            ),
            output_field=DecimalField(max_digits=16, decimal_places=3),
        ),
        concentration=ExpressionWrapper(
            Cast(F("fraction"), output_field=FloatField()) * 100,
            output_field=DecimalField(max_digits=5, decimal_places=1),
        ),
    ).annotate(
        price_per_active=ExpressionWrapper(
            F("price") / Cast(total_active_safe, output_field=FloatField()),
            output_field=DecimalField(max_digits=20, decimal_places=10),
        ),
    )


def public_catalog_products_with_stats(
    price_source: PriceSource,
    active_slug: str | None = None,
) -> QuerySet[Product]:
    """Return public catalog products annotated with catalog-facing metrics.

    The slug is resolved here and nowhere else, so a slug the catalog does not
    know about yields empty metrics instead of silently falling back.
    """
    queryset = (
        Product.objects.select_related("brand", "category")
        .prefetch_related("tags", "nutrition_profiles__flavors")
        .annotate(
            nutrition_profile_id=F("nutrition_profiles__id"),
            nutrition_facts_id=F("nutrition_profiles__nutrition_facts_id"),
        )
    )
    return _annotate_catalog_metrics(
        _annotate_catalog_base_fields(
            queryset,
            catalog_active(active_slug),
            price_source,
        ),
    )


SORTABLE_CATALOG_FIELDS = frozenset(
    {
        "price_per_active",
        "price",
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

    profile_matches = ProductNutrition.objects.filter(
        pk=OuterRef("nutrition_profile_id"),
        flavors__name__icontains=filters.search,
    )
    return (
        queryset.alias(profile_matches=Exists(profile_matches))
        .filter(
            Q(name__icontains=filters.search)
            | Q(brand__name__icontains=filters.search)
            | Q(category__name__icontains=filters.search)
            | Q(tags__name__icontains=filters.search)
            | Q(profile_matches=True)
            | Q(description__icontains=filters.search),
        )
        .distinct()
    )


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
        ("price__gte", filters.price_min),
        ("price__lte", filters.price_max),
        (
            "price_per_active__gte",
            filters.price_per_active_min,
        ),
        (
            "price_per_active__lte",
            filters.price_per_active_max,
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
    ordering = F("comparison_price" if sort_by == "price" else sort_by)
    stable_fallback = ["brand__name", "name", "pk", "nutrition_profile_id"]

    if sort_dir == "desc":
        return queryset.order_by(ordering.desc(nulls_last=True), *stable_fallback)
    return queryset.order_by(ordering.asc(nulls_last=True), *stable_fallback)


def public_catalog_products(
    price_source: PriceSource,
    filters: CatalogProductsFilters | None = None,
) -> QuerySet[Product]:
    """Return the public catalog queryset with filters and sorting applied."""
    resolved_filters = filters or CatalogProductsFilters()
    queryset = public_catalog_products_with_stats(
        price_source,
        resolved_filters.active,
    ).filter(is_published=True)
    queryset = _apply_catalog_search(queryset, resolved_filters)
    queryset = _apply_catalog_brand_filter(queryset, resolved_filters)
    queryset = _apply_catalog_numeric_filters(queryset, resolved_filters)
    return _apply_catalog_sorting(queryset, resolved_filters)
