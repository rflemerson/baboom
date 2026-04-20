"""URL routes for public frontend REST endpoints."""

from django.urls import path

from .views import catalog_products, subscribe_alerts

urlpatterns = [
    path("catalog/products/", catalog_products, name="catalog-products"),
    path("alerts/subscribe/", subscribe_alerts, name="subscribe-alerts"),
]
