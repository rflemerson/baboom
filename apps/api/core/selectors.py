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


def public_catalog_products_with_stats() -> QuerySet[Product]:
    """Return the public catalog queryset annotated with catalog-facing statistics.

    Annotations:
    - last_price
    - external_link
    - nutrition info
    - price_per_gram
    """
    latest_prices = ProductPriceHistory.objects.filter(
        store_product_link__product=OuterRef("pk"),
    ).order_by("-collected_at")

    nutrition_info = NutritionFacts.objects.filter(
        product_profiles__product=OuterRef("pk"),
    ).values("proteins", "serving_size_grams")[:1]

    # 1. Protect serving size against zero
    serving_safe = NullIf(F("serving_size_val"), Value(0))

    # 2. Protect Total Protein against zero (for protein/g calculation)
    protein_safe = NullIf(F("total_protein"), Value(0))

    return (
        Product.objects.select_related("brand", "category")
        .prefetch_related("tags")
        .annotate(
            last_price=Subquery(
                latest_prices.values("price")[:1],
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            external_link=Subquery(
                latest_prices.values("store_product_link__product_link")[:1],
                output_field=URLField(),
            ),
            per_serving_protein=Subquery(
                nutrition_info.values("proteins"),
                output_field=DecimalField(max_digits=5, decimal_places=1),
            ),
            serving_size_val=Subquery(
                nutrition_info.values("serving_size_grams"),
                output_field=DecimalField(max_digits=5, decimal_places=1),
            ),
        )
        .annotate(
            total_protein=ExpressionWrapper(
                (
                    F("weight")
                    * Cast(F("per_serving_protein"), output_field=FloatField())
                )
                / Cast(serving_safe, output_field=FloatField()),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            concentration=ExpressionWrapper(
                (
                    Cast(F("per_serving_protein"), output_field=FloatField())
                    / Cast(serving_safe, output_field=FloatField())
                )
                * 100,
                output_field=DecimalField(max_digits=5, decimal_places=1),
            ),
        )
        .annotate(
            price_per_gram=ExpressionWrapper(
                F("last_price") / Cast(protein_safe, output_field=FloatField()),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
    )
