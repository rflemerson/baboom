from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .api_views import ProductViewSet

router = SimpleRouter()
router.register(r"products", ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
]
