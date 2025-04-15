from rest_framework import serializers
from .models import (
    Brand,
    Store,
    Flavor,
    TagCategory,
    Tag,
    Product,
    ProductStore,
    ProductPriceHistory,
    NutritionalInfo,
    AdditionalNutrient,
    ProductFlavorNutritionalInfo,
)


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "display_name", "description"]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "name", "display_name", "description"]


class FlavorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flavor
        fields = ["id", "name", "description"]


class TagCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TagCategory
        fields = ["id", "name", "description"]


class TagSerializer(serializers.ModelSerializer):
    category = TagCategorySerializer(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "category", "description"]


class AdditionalNutrientSerializer(serializers.ModelSerializer):
    unit_display = serializers.CharField(source="get_unit_display", read_only=True)

    class Meta:
        model = AdditionalNutrient
        exclude = ["nutritional_info"]


class NutritionalInfoSerializer(serializers.ModelSerializer):
    additional_nutrients = AdditionalNutrientSerializer(many=True, read_only=True)

    class Meta:
        model = NutritionalInfo
        exclude = ["product"]  # Exclude product to avoid circular reference


class ProductPriceHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for product price history entries.
    Handles creating price history records with store relationships.
    """

    store = serializers.SerializerMethodField()
    store_id = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        write_only=True,
    )
    stock_status_display = serializers.CharField(
        source="get_stock_status_display", read_only=True
    )
    product = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductPriceHistory
        fields = [
            "id",
            "store",
            "store_id",
            "price",
            "stock_status",
            "stock_status_display",
            "collected_at",
            "product",
        ]
        read_only_fields = ["collected_at"]

    def get_store(self, obj):
        return StoreSerializer(obj.store_link.store).data

    def get_product(self, obj):
        return {"id": obj.store_link.product.id, "name": str(obj.store_link.product)}

    def create(self, validated_data):
        """
        Create a new price history entry with proper store link.
        """
        store = validated_data.pop("store_id")
        product_id = self.context.get("product_id")

        try:
            product = Product.objects.get(id=product_id)

            # Get or create the ProductStore link
            store_link, _ = ProductStore.objects.get_or_create(
                product=product, store=store, defaults={"product_link": ""}
            )

            # Create the price history entry
            price_history = ProductPriceHistory.objects.create(
                store_link=store_link, **validated_data
            )
            return price_history

        except Product.DoesNotExist:
            raise serializers.ValidationError(
                f"Product with ID {product_id} does not exist"
            )


class ProductStoreSerializer(serializers.ModelSerializer):
    """
    Serializer for product-store relationship.
    """

    store = StoreSerializer(read_only=True)

    class Meta:
        model = ProductStore
        fields = ["id", "store", "affiliate_link", "product_link"]


class ProductFlavorNutritionalInfoSerializer(serializers.ModelSerializer):
    flavor = FlavorSerializer(read_only=True)
    nutritional_info = NutritionalInfoSerializer(read_only=True)

    class Meta:
        model = ProductFlavorNutritionalInfo
        exclude = ["product"]


class ProductSerializer(serializers.ModelSerializer):
    """
    Main product serializer with calculated fields and related entities.
    Read-only for API consumption.
    """

    # Basic fields
    brand = BrandSerializer(read_only=True)
    packaging_display = serializers.CharField(
        source="get_packaging_display", read_only=True
    )

    # Related information
    tags = TagSerializer(many=True, read_only=True)
    nutritional_infos = NutritionalInfoSerializer(many=True, read_only=True)
    flavor_nutritional_infos = ProductFlavorNutritionalInfoSerializer(
        source="productflavornutritionalinfo_set", many=True, read_only=True
    )

    # Store information
    stores = ProductStoreSerializer(
        source="productstore_set", many=True, read_only=True
    )

    # Price information (latest only)
    current_price = serializers.SerializerMethodField()

    # For protein products - can be determined by tags now
    protein_concentration = serializers.SerializerMethodField()
    total_protein = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "brand",
            "name",
            "weight",
            "packaging",
            "packaging_display",
            "tags",
            "nutritional_infos",
            "flavor_nutritional_infos",
            "stores",
            "current_price",
            "protein_concentration",
            "total_protein",
        ]
        read_only_fields = fields  # All fields are read-only for API consumption

    def get_current_price(self, obj):
        """Get the most recent price entry for this product across all stores."""
        latest_prices = []
        for store_link in obj.productstore_set.all():
            latest_price = store_link.price_history.order_by("-collected_at").first()
            if latest_price:
                latest_prices.append(
                    {
                        "store": store_link.store.name,
                        "price": latest_price.price,
                        "collected_at": latest_price.collected_at,
                    }
                )

        return latest_prices if latest_prices else None

    def get_protein_concentration(self, obj):
        """Calculate protein concentration percentage for protein products."""
        # Check if this is a protein product by looking at tags
        is_protein_product = obj.tags.filter(
            category__name__icontains="protein"
        ).exists()

        if not is_protein_product:
            return None

        # Get the first nutritional info
        ni = obj.nutritional_infos.first()
        if (
            ni
            and ni.serving_size_grams
            and ni.serving_size_grams > 0
            and ni.proteins is not None
        ):
            try:
                concentration = (float(ni.proteins) / ni.serving_size_grams) * 100
                return round(concentration, 1)
            except (ZeroDivisionError, ValueError):
                return None
        return None

    def get_total_protein(self, obj):
        """Calculate total protein content in grams for the entire product."""
        concentration = self.get_protein_concentration(obj)
        if concentration is not None and obj.weight is not None:
            total_protein = obj.weight * (concentration / 100)
            return round(total_protein, 1)
        return None
