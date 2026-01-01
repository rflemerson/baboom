from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .filters import ProductFilter
from .models import Product

DEFAULT_PER_PAGE = 12
PER_PAGE_OPTIONS = [12, 24, 48]


def product_list(request: HttpRequest) -> HttpResponse:
    products_qs = Product.objects.with_stats()
    product_filter = ProductFilter(request.GET, queryset=products_qs)

    # Get items per page from request, validate against allowed options
    try:
        per_page = int(request.GET.get("per_page", DEFAULT_PER_PAGE))
        if per_page not in PER_PAGE_OPTIONS:
            per_page = DEFAULT_PER_PAGE
    except (ValueError, TypeError):
        per_page = DEFAULT_PER_PAGE

    paginator = Paginator(product_filter.qs, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "filter": product_filter,
        "products": page_obj,
        "page_obj": page_obj,
        "per_page": per_page,
    }

    if getattr(request, "htmx", False):
        template_name = "core/partials/product_list_results.html"
    else:
        template_name = "core/product_list.html"

    return render(request, template_name, context)
