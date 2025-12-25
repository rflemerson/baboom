from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .filters import ProductFilter
from .models import Product


def product_list(request: HttpRequest) -> HttpResponse:
    products_qs = Product.objects.with_stats()
    product_filter = ProductFilter(request.GET, queryset=products_qs)

    context = {
        "filter": product_filter,
        "products": product_filter.qs,
    }

    if getattr(request, "htmx", False):
        template_name = "core/partials/product_list_results.html"
    else:
        template_name = "core/product_list.html"

    return render(request, template_name, context)
