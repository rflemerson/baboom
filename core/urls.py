from django.urls import path

from . import views

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("subscribe/", views.subscribe_alerts, name="subscribe_alerts"),
    path("playground/", views.components_playground, name="components_playground"),
]
