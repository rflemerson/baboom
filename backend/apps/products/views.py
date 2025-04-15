from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Prefetch, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import (
    Product,
    ProductPriceHistory,
)
from .serializers import (
    ProductSerializer,
    ProductPriceHistorySerializer,
)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing products.
    """

    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "brand__name", "tags__name"]

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        """List products with optional caching."""
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a product with optional caching."""
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        """
        Optimizes the query and allows filtering by tags.
        """
        queryset = Product.objects.select_related(
            "brand",  # For brand details
        ).prefetch_related(
            "tags__category",  # For tags with their categories
            Prefetch(
                "productstore_set",
                queryset=Product.productstore_set.related.model.objects.select_related(
                    "store"
                ),
            ),
            Prefetch(
                "productstore_set__price_history",
                queryset=ProductPriceHistory.objects.order_by("-collected_at"),
            ),
            "nutritional_infos__additional_nutrients",  # For nutritional info with additional nutrients
            "productflavornutritionalinfo_set__flavor",  # For flavor information
            "productflavornutritionalinfo_set__nutritional_info",  # For flavor-specific nutritional info
        )

        # Filter by tag category
        tag_category = self.request.query_params.get("tag_category")
        if tag_category:
            queryset = queryset.filter(tags__category__name__icontains=tag_category)

        # Filter by tag name
        tag_name = self.request.query_params.get("tag")
        if tag_name:
            queryset = queryset.filter(tags__name__icontains=tag_name)

        # Filter by brand
        brand_id = self.request.query_params.get("brand_id")
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)

        # Filter by name
        name = self.request.query_params.get("name")
        if name:
            queryset = queryset.filter(name__icontains=name)

        # Ensure distinct results when filtering by tag
        if tag_category or tag_name:
            queryset = queryset.distinct()

        return queryset

    @action(
        detail=True,
        methods=["post"],
        url_path="prices",
        serializer_class=ProductPriceHistorySerializer,
        permission_classes=[permissions.IsAuthenticated],
    )
    def add_price(self, request, pk=None):
        """
        Add a new price record for a product.
        Requires authentication.
        """
        product = self.get_object()
        serializer = self.get_serializer(
            data=request.data, context={"product_id": product.id}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["get"],
        url_path="prices",
        serializer_class=ProductPriceHistorySerializer,
    )
    def get_prices(self, request, pk=None):
        """
        Return the price history for a product.
        """
        product = self.get_object()
        price_history = ProductPriceHistory.objects.filter(
            store_link__product=product
        ).order_by("-collected_at")

        # Handle pagination if there are many prices
        page = self.paginate_queryset(price_history)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(price_history, many=True)
        return Response(serializer.data)
