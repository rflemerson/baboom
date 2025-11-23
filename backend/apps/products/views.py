from django.shortcuts import render
from .models import Product


def product_list(request):
    from django.db.models import Min, OuterRef, Subquery, F, ExpressionWrapper, DecimalField
    from .models import ProductPriceHistory, NutritionalInfo

    # Subquery to get the latest price for each product-store link
    latest_prices = ProductPriceHistory.objects.filter(
        store_product_link__product=OuterRef("pk")
    ).order_by("-collected_at")

    # Subquery to get protein content and serving size
    nutrition_info = NutritionalInfo.objects.filter(
        product_profile__product=OuterRef("pk")
    ).values("proteins", "serving_size_grams")[:1]

    products = (
        Product.objects.select_related("brand", "category")
        .prefetch_related("tags")
        .annotate(
            last_price=Subquery(latest_prices.values("price")[:1]),
            total_protein=Subquery(nutrition_info.values("proteins")),
            serving_size=Subquery(nutrition_info.values("serving_size_grams")),
        )
        .annotate(
            price_per_gram=ExpressionWrapper(
                F("last_price") / F("total_protein"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            concentration=ExpressionWrapper(
                (F("total_protein") / F("serving_size")) * 100,
                output_field=DecimalField(max_digits=5, decimal_places=1),
            ),
        )
        .all()
    )

    template_name = "products/list.html"
    if request.htmx:
        template_name = "products/_product_list.html"

    return render(request, template_name, {"products": products})
