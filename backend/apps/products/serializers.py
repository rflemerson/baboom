from drf_spectacular.utils import extend_schema_field
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
    AdditionalNutrient,
    ProductNutritionProfile,
)


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        exclude = ["id"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        exclude = ["id"]


class AdditionalNutrientSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdditionalNutrient
        exclude = ["id"]


class NutritionalInfoSerializer(serializers.ModelSerializer):
    additional_components = AdditionalNutrientSerializer(
        source="additionalnutrient_set", many=True, read_only=True
    )

    class Meta:
        model = NutritionalInfo
        exclude = ["id", "product_profile"]


class ProductNutritionProfileSerializer(serializers.ModelSerializer):
    nutritional_info = NutritionalInfoSerializer(
        source="nutritionalinfo_set", many=True, read_only=True
    )

    flavors = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = ProductNutritionProfile
        exclude = ["id", "product"]


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    stock_status_display = serializers.CharField(
        source="get_stock_status_display", read_only=True
    )
    store_name = serializers.CharField(
        source="store_product_link.store.name", read_only=True
    )

    class Meta:
        model = ProductPriceHistory
        exclude = ["id"]
        read_only_fields = ["collected_at"]
        extra_kwargs = {
            "store_product_link": {"write_only": True},
        }


class ProductStoreSerializer(serializers.ModelSerializer):
    store = StoreSerializer(read_only=True)
    latest_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductStore
        exclude = ["id", "product"]

    @extend_schema_field(dict)
    def get_latest_price(self, obj):
        latest = obj.productpricehistory_set.order_by("-collected_at").first()
        if not latest:
            return None
        return {
            "price": latest.price,
            "collected_at": latest.collected_at,
            "stock_status": latest.get_stock_status_display(),
        }


class ProductSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    category = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    stores = ProductStoreSerializer(
        source="productstore_set", many=True, read_only=True
    )
    nutrition_profiles = ProductNutritionProfileSerializer(
        source="productnutritionprofile_set", many=True, read_only=True
    )

    class Meta:
        model = Product
        fields = "__all__"

    @extend_schema_field(dict)
    def get_category(self, obj):
        return Category.dump_bulk()

    @extend_schema_field(dict)
    def get_tags(self, obj):
        return Tag.dump_bulk()
