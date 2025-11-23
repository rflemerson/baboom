from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import Product, ProductStore, ProductNutritionProfile
from .serializers import (
    ProductSerializer,
    ProductPriceHistorySerializer,
)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing product information.

    Provides 'list' and 'retrieve' actions by default, plus custom endpoints
    for adding price information and retrieving nutrition profiles.
    """

    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(60 * 5))  # Cache list view for 5 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))  # Cache detail view for 15 minutes
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        """
        Get the queryset for products with optimized database access.
        Optionally filters by brand_id if provided in query parameters.
        """
        qs = Product.objects.select_related("brand", "category").prefetch_related(
            Prefetch(
                "productstore_set",
                queryset=ProductStore.objects.select_related("store").prefetch_related(
                    "productpricehistory_set"
                ),
            ),
            Prefetch(
                "productnutritionprofile_set",
                queryset=ProductNutritionProfile.objects.prefetch_related(
                    "flavors",
                    "nutritionalinfo_set__additionalnutrient_set",
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
        """
        Add price information for a specific product at a specific store.

        Requires authentication. The store_id and price must be provided
        in the request data.
        """
        product = self.get_object()
        store_id = request.data.get("store_id")
        price = request.data.get("price")

        if not store_id or price is None:
            return Response(
                {"error": "store_id and price are required fields"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = ProductStore.objects.get(product=product, store_id=store_id)
        except ProductStore.DoesNotExist:
            return Response(
                {"error": "Product-store relationship does not exist"},
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
