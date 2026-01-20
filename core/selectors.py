from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    QuerySet,
    Subquery,
    URLField,
)
from django.db.models.functions import Cast

from .models import NutritionFacts, Product, ProductPriceHistory


def list_with_stats() -> QuerySet[Product]:
    """
    Returns a Product QuerySet annotated with:
    - last_price
    - external_link
    - nutrition info
    - price_per_gram
    """
    latest_prices = ProductPriceHistory.objects.filter(
        store_product_link__product=OuterRef("pk")
    ).order_by("-collected_at")

    nutrition_info = NutritionFacts.objects.filter(
        product_profiles__product=OuterRef("pk")
    ).values("proteins", "serving_size_grams")[:1]

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
                / Cast(F("serving_size_val"), output_field=FloatField()),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            concentration=ExpressionWrapper(
                (
                    Cast(F("per_serving_protein"), output_field=FloatField())
                    / Cast(F("serving_size_val"), output_field=FloatField())
                )
                * 100,
                output_field=DecimalField(max_digits=5, decimal_places=1),
            ),
        )
        .annotate(
            price_per_gram=ExpressionWrapper(
                F("last_price") / F("total_protein"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
    )
