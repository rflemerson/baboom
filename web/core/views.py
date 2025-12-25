from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from .models import Product


def product_list(request: HttpRequest) -> HttpResponse:
    products = Product.objects.with_stats()

    template_name = "core/product_list.html"

    return render(request, template_name, {"products": products})
