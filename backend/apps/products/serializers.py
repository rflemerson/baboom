from rest_framework import serializers
from .models import (
    Brand,
    Store,
    Flavor,
    Tag,
    Category,
    Product,
    ProductStore,
    ProductPriceHistory,
    NutritionalInfo,
)


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "display_name"]
        read_only_fields = ["id"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "name", "display_name"]
        read_only_fields = ["id"]


class FlavorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flavor
        fields = ["id", "name"]
        read_only_fields = ["id"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]
        read_only_fields = ["id"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = ["id"]


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    stock_status_display = serializers.CharField(
        source="get_stock_status_display", read_only=True
    )
    store_name = serializers.CharField(
        source="store_product_link.store.name", read_only=True
    )

    class Meta:
        model = ProductPriceHistory
        fields = [
            "id",
            "price",
            "stock_status",
            "stock_status_display",
            "collected_at",
            "store_name",
            "store_product_link",
        ]
        read_only_fields = ["id", "collected_at"]
        extra_kwargs = {"store_product_link": {"write_only": True}}


class ProductStoreSerializer(serializers.ModelSerializer):
    store = StoreSerializer(read_only=True)
    latest_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductStore
        fields = ["id", "store", "product_link", "latest_price"]
        read_only_fields = ["id"]

    def get_latest_price(self, obj):
        latest = obj.price_histories.order_by("-collected_at").first()
        return {
            "price": latest.price if latest else None,
            "collected_at": latest.collected_at if latest else None,
            "stock_status": latest.get_stock_status_display() if latest else None,
        }


class NutritionalInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionalInfo
        fields = ["id", "serving_size_grams", "proteins", "carbohydrates", "total_fats"]
        read_only_fields = ["id"]


class ProductSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    stores = ProductStoreSerializer(source="store_links", many=True, read_only=True)
    packaging_display = serializers.CharField(
        source="get_packaging_display", read_only=True
    )
    protein_concentration = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "brand",
            "name",
            "weight",
            "packaging",
            "packaging_display",
            "category",
            "stores",
            "protein_concentration",
        ]
        read_only_fields = ["id"]

    def get_protein_concentration(self, obj):
        nutritional_profile = obj.nutritional_profiles.first()
        if not nutritional_profile or nutritional_profile.serving_size_grams <= 0:
            return None
        try:
            return round(
                (
                    float(nutritional_profile.proteins)
                    / nutritional_profile.serving_size_grams
                )
                * 100,
                1,
            )
        except (TypeError, ValueError, ZeroDivisionError):
            return None
