"""Selectors for public catalog querysets and annotations."""

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    QuerySet,
    Subquery,
    URLField,
    Value,
)
from django.db.models.functions import Cast, NullIf

from .models import NutritionFacts, Product, ProductPriceHistory


def _latest_price_history_subquery() -> QuerySet[ProductPriceHistory]:
    """Return the latest price history rows for the outer product."""
    return ProductPriceHistory.objects.filter(
        store_product_link__product=OuterRef("pk"),
    ).order_by("-collected_at")


def _catalog_nutrition_facts_subquery() -> QuerySet[NutritionFacts]:
    """Return the deterministic nutrition facts rows used by the public catalog."""
    return NutritionFacts.objects.filter(
        product_profiles__product=OuterRef("pk"),
    ).order_by("id")


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
