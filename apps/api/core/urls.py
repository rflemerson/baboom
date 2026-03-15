from django.urls import path

from . import views

urlpatterns = [
    path("", views.list_view, name="list"),
    path("subscribe/", views.subscribe_alerts, name="subscribe_alerts"),
]
