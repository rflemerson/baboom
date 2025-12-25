from django.db import models
from simple_history.models import HistoricalRecords
from treebeard.mp_tree import MP_Node


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    display_name = models.CharField(
        max_length=100, unique=True, verbose_name="Display Name"
    )
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Brand description"
    )

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"
        ordering = ["name"]

    def __str__(self):
        return self.display_name


class Store(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    display_name = models.CharField(
        max_length=100, unique=True, verbose_name="Display Name"
    )
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Store description"
    )

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"
        ordering = ["name"]

    def __str__(self):
        return self.display_name


class Flavor(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Flavor description"
    )

    class Meta:
        verbose_name = "Flavor"
        verbose_name_plural = "Flavors"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(MP_Node):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Name",
        help_text="Unique tag name",
    )
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Tag description"
    )

    node_order_by = ["name"]

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name


class Category(MP_Node):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Name",
        help_text="Unique category name",
    )
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Category description"
    )

    node_order_by = ["name"]

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    PACKAGING_CHOICES = [
        ("REFILL", "Refill Package"),
        ("CONTAINER", "Container Package"),
    ]

    name = models.CharField(max_length=200, verbose_name="Product Name")

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name="Brand")

    weight = models.PositiveIntegerField(
        verbose_name="Weight (grams)", help_text="Total product weight in grams"
    )
    packaging = models.CharField(
        max_length=20,
        choices=PACKAGING_CHOICES,
        verbose_name="Packaging Type",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Product Category",
    )

    stores = models.ManyToManyField(
        Store,
        through="ProductStore",
        verbose_name="Available In Stores",
        blank=True,
    )

    tags = models.ManyToManyField(Tag, verbose_name="Product Tags", blank=True)

    class Meta:
        unique_together = [["brand", "name"]]
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["brand__name", "name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["brand", "name"]),
        ]

    def __str__(self):
        return f"{self.brand.name} - {self.name} ({self.weight}g)"


class ProductStore(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="Related Product",
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        verbose_name="Associated Store",
    )

    external_id = models.CharField(
        max_length=100,
        verbose_name="Store Product ID",
        help_text="Unique identifier in store system (e.g., SKU)",
        blank=True,
    )

    product_link = models.URLField(
        verbose_name="Store Product URL",
        help_text="Direct URL to product page in the store",
    )

    affiliate_link = models.URLField(
        verbose_name="Affiliate Tracking URL",
        help_text="URL with affiliate tracking parameters",
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = [["product", "store"], ["store", "external_id"]]

        verbose_name = "Store Product Link"
        verbose_name_plural = "Store Product Links"

        ordering = ["store__name", "product__name"]

        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["store", "product"]),
        ]

    def __str__(self):
        return f"{self.store.name} → {self.product.name}"


class ProductPriceHistory(models.Model):
    STOCK_STATUS_CHOICES = [
        ("A", "Available"),
        ("L", "Last Units"),
        ("O", "Out of Stock"),
    ]

    store_product_link = models.ForeignKey(
        ProductStore,
        on_delete=models.CASCADE,
        verbose_name="Store Product Link",
        help_text="Link to specific product-store combination",
    )

    price = models.DecimalField(
        verbose_name="Current Price",
        max_digits=10,
        decimal_places=2,
        help_text="Price in local currency",
    )

    stock_status = models.CharField(
        verbose_name="Inventory Status",
        max_length=1,
        choices=STOCK_STATUS_CHOICES,
        default="A",
        help_text="Current availability status",
    )

    collected_at = models.DateTimeField(
        verbose_name="Collection Timestamp",
        auto_now_add=True,
        help_text="Automatic timestamp when record was created",
    )

    history = HistoricalRecords(
        verbose_name="Version History",
        excluded_fields=["history"],
        history_change_reason_field=models.TextField(
            null=True, blank=True, verbose_name="Change Reason"
        ),
    )

    class Meta:
        ordering = ["-collected_at"]
        get_latest_by = "collected_at"
        unique_together = [["store_product_link", "collected_at"]]
        verbose_name = "Price Tracking Record"
        verbose_name_plural = "Price Tracking Records"
        indexes = [
            models.Index(fields=["collected_at"]),
            models.Index(fields=["stock_status"]),
            models.Index(fields=["store_product_link", "collected_at"]),
        ]

    def __str__(self):
        return f"{self.store_product_link} | {self.get_stock_status_display()} @ {self.collected_at:%Y-%m-%d %H:%M}"


class NutritionalInfo(models.Model):
    product_profile = models.ForeignKey(
        "ProductNutritionProfile",
        on_delete=models.CASCADE,
        verbose_name="Product Nutrition Profile",
        help_text="Product profile associated with this nutritional information",
    )

    description = models.CharField(max_length=200, verbose_name="Description")

    serving_size_grams = models.PositiveSmallIntegerField(
        verbose_name="Serving Size (g)"
    )

    energy_kcal = models.PositiveSmallIntegerField(verbose_name="Energy Content (kcal)")

    carbohydrates = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Carbohydrates (g)"
    )

    total_sugars = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Total Sugars (g)"
    )

    added_sugars = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Added Sugars (g)"
    )

    proteins = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Protein Content (g)"
    )

    total_fats = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Total Fats (g)"
    )

    saturated_fats = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Saturated Fats (g)"
    )

    trans_fats = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Trans Fats (g)"
    )

    dietary_fiber = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="Dietary Fiber (g)"
    )

    sodium = models.PositiveIntegerField(verbose_name="Sodium Content (mg)")

    class Meta:
        verbose_name = "Nutritional Information"
        verbose_name_plural = "Nutritional Information tables"
        constraints = [
            models.UniqueConstraint(
                fields=["product_profile"], name="unique_nutritional_info_per_profile"
            )
        ]

    def __str__(self):
        return f"{self.description} - {self.serving_size_grams}g"


class AdditionalNutrient(models.Model):
    MEASUREMENT_UNITS = [
        ("g", "Grams"),
        ("mg", "Milligrams"),
        ("mcg", "Micrograms"),
        ("IU", "International Units"),
        ("%", "Daily Value Percentage"),
    ]

    nutritional_profile = models.ForeignKey(
        NutritionalInfo,
        on_delete=models.CASCADE,
        verbose_name="Nutritional Profile",
        help_text="Associated nutritional profile",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="Nutrient Name",
        help_text="e.g., Vitamin C, Iron, Zinc",
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Nutrient Quantity",
        help_text="Measured amount per serving",
    )

    unit = models.CharField(
        max_length=10,
        choices=MEASUREMENT_UNITS,
        default="mg",
        verbose_name="Measurement Unit",
        help_text="Unit of measurement for this nutrient",
    )

    class Meta:
        unique_together = [["nutritional_profile", "name"]]
        verbose_name = "Micronutrient Data"
        verbose_name_plural = "Micronutrients Data"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.nutritional_profile} | {self.name} ({self.get_unit_display()})"


class ProductNutritionProfile(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="Base Product",
        help_text="Product associated with this nutritional profile",
    )

    flavors = models.ManyToManyField(
        "Flavor",
        verbose_name="Flavors",
        help_text="Flavors associated with this nutritional profile",
        blank=True,
    )

    class Meta:
        verbose_name = "Product Nutrition Profile"
        verbose_name_plural = "Product Nutrition Profiles"
        ordering = ["product__name"]

    def __str__(self):
        return f"{self.product.name}"
