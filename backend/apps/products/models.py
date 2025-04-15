from django.db import models
from simple_history.models import HistoricalRecords


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    display_name = models.CharField(
        max_length=100, unique=True, verbose_name="Display Name"
    )
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Description of the brand"
    )

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"

    def __str__(self):
        return self.name


class Store(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    display_name = models.CharField(
        max_length=100, unique=True, verbose_name="Display Name"
    )
    description = models.TextField(
        blank=True, verbose_name="Description", help_text="Description of the store"
    )

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"

    def __str__(self):
        return self.name


class Flavor(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Flavor"
        verbose_name_plural = "Flavors"

    def __str__(self):
        return self.name


class TagCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        verbose_name = "Tag Category"
        verbose_name_plural = "Tag Categories"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Tag Name")
    category = models.ForeignKey(
        TagCategory,
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name="Category",
    )
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return f"{self.name} ({self.category.name})"


class Product(models.Model):
    PACKAGING_CHOICES = [
        ("R", "Refill"),
        ("C", "Container"),
    ]

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name="Brand")
    name = models.CharField(max_length=200, verbose_name="Name")
    weight = models.PositiveIntegerField(
        verbose_name="Weight (g)", help_text="Total weight in grams"
    )
    packaging = models.CharField(
        max_length=1, choices=PACKAGING_CHOICES, verbose_name="Packaging"
    )

    stores = models.ManyToManyField(
        Store,
        through="ProductStore",
        related_name="products",
        verbose_name="Available Stores",
    )

    flavors = models.ManyToManyField(
        Flavor,
        through="ProductFlavorNutritionalInfo",
        related_name="products",
        verbose_name="Available Flavors",
    )

    tags = models.ManyToManyField(
        Tag, related_name="products", blank=True, verbose_name="Tags"
    )

    class Meta:
        unique_together = [["brand", "name"]]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return f"{self.brand} - {self.name}"


class ProductStore(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, verbose_name="Store")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name="Product"
    )
    affiliate_link = models.URLField("Affiliate Link", null=True, blank=True)
    product_link = models.URLField("Product Link")

    class Meta:
        unique_together = [["product", "store"]]
        verbose_name = "Product Store Link"
        verbose_name_plural = "Product Store Links"

    def __str__(self):
        return f"{self.product} | {self.store}"


class ProductPriceHistory(models.Model):
    STOCK_STATUS_CHOICES = [
        ("A", "Available"),
        ("L", "Last Units"),
        ("O", "Out of Stock"),
    ]

    store_link = models.ForeignKey(
        ProductStore,
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name="Store Link",
    )
    price = models.DecimalField("Price", max_digits=10, decimal_places=2)
    stock_status = models.CharField(
        "Stock Status", max_length=1, choices=STOCK_STATUS_CHOICES, default="A"
    )
    collected_at = models.DateTimeField("Collected at", auto_now_add=True)

    history = HistoricalRecords(
        verbose_name="History",
        excluded_fields=["history"],
        history_change_reason_field=models.TextField(null=True, blank=True),
    )

    class Meta:
        ordering = ["-collected_at"]
        get_latest_by = "collected_at"
        unique_together = [["store_link", "collected_at"]]
        verbose_name = "Price and Stock History"
        verbose_name_plural = "Price and Stock History"
        indexes = [
            models.Index(fields=["collected_at"]),
            models.Index(fields=["stock_status"]),
        ]

    def __str__(self):
        return f"{self.store_link} | ${self.price} ({self.collected_at})"


class NutritionalInfo(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="nutritional_infos",
        verbose_name="Product",
    )
    serving_size_grams = models.PositiveSmallIntegerField(
        verbose_name="Serving size (g)"
    )
    energy_kcal = models.PositiveSmallIntegerField(verbose_name="Energy value (kcal)")
    carbohydrates = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Carbohydrates (g)"
    )
    total_sugars = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Total sugars (g)"
    )
    added_sugars = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Added sugars (g)"
    )
    proteins = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Proteins (g)"
    )
    total_fats = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Total fats (g)"
    )
    saturated_fats = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Saturated fats (g)"
    )
    trans_fats = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Trans fats (g)"
    )
    dietary_fiber = models.DecimalField(
        max_digits=4, decimal_places=1, verbose_name="Dietary fiber (g)"
    )
    sodium = models.PositiveIntegerField(verbose_name="Sodium (mg)")

    class Meta:
        verbose_name = "Nutritional Information"
        verbose_name_plural = "Nutritional Information"

    def __str__(self):
        return f"{self.product} - {self.serving_size_grams}g"


class AdditionalNutrient(models.Model):
    COMMON_UNITS = [
        ("g", "grams"),
        ("mg", "milligrams"),
        ("mcg", "micrograms"),
        ("IU", "international units"),
        ("%", "percentage"),
    ]

    nutritional_info = models.ForeignKey(
        NutritionalInfo,
        on_delete=models.CASCADE,
        related_name="additional_nutrients",
        verbose_name="Nutritional Information",
    )
    name = models.CharField(max_length=100, verbose_name="Nutrient")
    value = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Value")
    unit = models.CharField(
        max_length=10, choices=COMMON_UNITS, default="mg", verbose_name="Unit"
    )

    class Meta:
        unique_together = [["nutritional_info", "name"]]
        verbose_name = "Additional Nutrient"
        verbose_name_plural = "Additional Nutrients"

    def __str__(self):
        return f"{self.name}: {self.value} {self.unit}"


class ProductFlavorNutritionalInfo(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name="Product"
    )
    flavor = models.ForeignKey(Flavor, on_delete=models.CASCADE, verbose_name="Flavor")
    nutritional_info = models.ForeignKey(
        NutritionalInfo,
        on_delete=models.CASCADE,
        verbose_name="Nutritional Information",
    )

    class Meta:
        unique_together = [["product", "flavor"]]
        verbose_name = "Flavor and Nutrition"
        verbose_name_plural = "Flavors and Nutrition"

    def __str__(self):
        return f"{self.product} - {self.flavor}"
