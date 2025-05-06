from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import Product, ProductStore, ProductPriceHistory, ProductNutritionProfile
from .serializers import (
    ProductSerializer,
    ProductPriceHistorySerializer,
    ProductNutritionProfileSerializer,
)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(60 * 5))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        qs = Product.objects.select_related("brand", "category").prefetch_related(
            Prefetch(
                "store_links",
                queryset=ProductStore.objects.select_related("store").prefetch_related(
                    "price_histories"
                ),
            ),
            Prefetch(
                "nutrition_profiles",
                queryset=ProductNutritionProfile.objects.select_related(
                    "nutritional_info"
                ).prefetch_related(
                    "flavors", "nutritional_info__additional_components"
                ),
            ),
        )
        brand_id = self.request.query_params.get("brand_id")
        if brand_id:
            qs = qs.filter(brand_id=brand_id)
        return qs

    @action(
        detail=True,
        methods=["post"],
        url_path="prices",
        serializer_class=ProductPriceHistorySerializer,
        permission_classes=[permissions.IsAuthenticated],
    )
    def add_price(self, request, pk=None):
        product = self.get_object()
        store_id = request.data.get("store_id")
        price = request.data.get("price")
        if not store_id or price is None:
            return Response(
                {"error": "store_id e price são campos obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            link = ProductStore.objects.get(product=product, store_id=store_id)
        except ProductStore.DoesNotExist:
            return Response(
                {"error": "Ligação produto-loja não existe"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ProductPriceHistorySerializer(
            data={
                "store_product_link": link.id,
                "price": price,
                "stock_status": request.data.get("stock_status", "A"),
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["get"],
        url_path="nutrition-profiles",
        serializer_class=ProductNutritionProfileSerializer,
    )
    def get_nutrition_profiles(self, request, pk=None):
        product = self.get_object()
        profiles = (
            ProductNutritionProfile.objects.filter(product=product)
            .select_related("nutritional_info")
            .prefetch_related("flavors", "nutritional_info__additional_components")
        )
        serializer = self.get_serializer(profiles, many=True)
        return Response(serializer.data)
