from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import (
    Product, ProductStore, ProductPriceHistory
)
from .serializers import (
    ProductSerializer, ProductPriceHistorySerializer
)

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("brand", "category")
            .prefetch_related(
                Prefetch(
                    "store_links",
                    queryset=ProductStore.objects.select_related("store").prefetch_related(
                        "price_histories"
                    ),
                ),
                "nutritional_profiles",
            )
        )
        
        # Aplicar filtros básicos
        brand_id = self.request.query_params.get("brand_id")
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
            
        return queryset

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
        
        if not store_id or not price:
            return Response(
                {"error": "store_id e price são campos obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            store_link = ProductStore.objects.get(product=product, store_id=store_id)
        except ProductStore.DoesNotExist:
            return Response(
                {"error": "Ligação produto-loja não existe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProductPriceHistorySerializer(data={
            "store_product_link": store_link.id,
            "price": price,
            "stock_status": request.data.get("stock_status", "A")
        })
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["get"],
        url_path="prices",
        serializer_class=ProductPriceHistorySerializer,
    )
    def get_prices(self, request, pk=None):
        product = self.get_object()
        latest_price = ProductPriceHistory.objects.filter(
            store_product_link__product=product
        ).order_by("-collected_at").first()

        if not latest_price:
            return Response(
                {"detail": "Nenhum histórico de preço disponível para este produto"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(latest_price)
        return Response(serializer.data)
