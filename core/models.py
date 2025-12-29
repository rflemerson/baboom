import logging

from django.db import models
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    Subquery,
    URLField,
)
from django.db.models.functions import Cast
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from treebeard.mp_tree import MP_Node

logger = logging.getLogger(__name__)


class Brand(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)
    display_name = models.CharField(_("Display Name"), max_length=100, unique=True)
    description = models.TextField(
        _("Description"), blank=True, help_text=_("Brand description")
    )

    class Meta:
        verbose_name = _("Brand")
        verbose_name_plural = _("Brands")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.display_name


class Store(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)
    display_name = models.CharField(_("Display Name"), max_length=100, unique=True)
    description = models.TextField(
        _("Description"), blank=True, help_text=_("Store description")
    )

    class Meta:
        verbose_name = _("Store")
        verbose_name_plural = _("Stores")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.display_name


class Flavor(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)
    description = models.TextField(
        _("Description"), blank=True, help_text=_("Flavor description")
    )

    class Meta:
        verbose_name = _("Flavor")
        verbose_name_plural = _("Flavors")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Tag(MP_Node):
    name: models.CharField = models.CharField(
        _("Name"), max_length=100, unique=True, help_text=_("Unique tag name")
    )
    description: models.TextField = models.TextField(
        _("Description"), blank=True, help_text=_("Tag description")
    )

    node_order_by = ["name"]

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")

    def __str__(self) -> str:
        return self.name


class Category(MP_Node):
    name: models.CharField = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
        help_text=_("Unique category name"),
    )
    description: models.TextField = models.TextField(
        _("Description"), blank=True, help_text=_("Category description")
    )

    node_order_by = ["name"]

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def with_stats(self) -> models.QuerySet:
        logger.debug("Calculating stats for ProductQuerySet")
        latest_prices = ProductPriceHistory.objects.filter(
            store_product_link__product=OuterRef("pk")
        ).order_by("-collected_at")

        nutrition_info = NutritionFacts.objects.filter(
            product_profiles__product=OuterRef("pk")
        ).values("proteins", "serving_size_grams")[:1]

        return (
            self.select_related("brand", "category")
            .prefetch_related("tags")
            .annotate(
                last_price=Subquery(
                    latest_prices.values("price")[:1],
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                external_link=Subquery(
                    latest_prices.values("store_product_link__product_link")[:1],
                    output_field=URLField(),
                ),
                per_serving_protein=Subquery(
                    nutrition_info.values("proteins"),
                    output_field=DecimalField(max_digits=5, decimal_places=1),
                ),
                serving_size_val=Subquery(
                    nutrition_info.values("serving_size_grams"),
                    output_field=DecimalField(max_digits=5, decimal_places=1),
                ),
            )
            .annotate(
                total_protein=ExpressionWrapper(
                    (
                        F("weight")
                        * Cast(F("per_serving_protein"), output_field=FloatField())
                    )
                    / Cast(F("serving_size_val"), output_field=FloatField()),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                concentration=ExpressionWrapper(
                    (
                        Cast(F("per_serving_protein"), output_field=FloatField())
                        / Cast(F("serving_size_val"), output_field=FloatField())
                    )
                    * 100,
                    output_field=DecimalField(max_digits=5, decimal_places=1),
                ),
            )
            .annotate(
                price_per_gram=ExpressionWrapper(
                    F("last_price") / F("total_protein"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
            )
        )


class Product(models.Model):
    class Packaging(models.TextChoices):
        REFILL = "REFILL", _("Refill Package")
        CONTAINER = "CONTAINER", _("Container Package")
        BAR = "BAR", _("Bar")
        OTHER = "OTHER", _("Other")

    name = models.CharField(_("Product Name"), max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name=_("Brand"))
    description = models.TextField(
        _("Description"), blank=True, help_text=_("Marketing description")
    )

    weight = models.PositiveIntegerField(
        _("Weight (grams)"), help_text=_("Total product weight in grams")
    )

    ean = models.CharField(
        _("EAN/GTIN"),
        max_length=14,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("European Article Number / Global Trade Item Number"),
    )

    packaging = models.CharField(
        _("Packaging Type"),
        max_length=20,
        choices=Packaging.choices,
        default=Packaging.CONTAINER,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Product Category"),
    )

    stores: models.ManyToManyField = models.ManyToManyField(
        Store,
        through="ProductStore",
        verbose_name=_("Available In Stores"),
        blank=True,
    )

    tags: models.ManyToManyField = models.ManyToManyField(
        Tag, verbose_name=_("Product Tags"), blank=True
    )

    is_manually_curated = models.BooleanField(
        _("Manually Curated"),
        default=False,
        help_text=_(
            "If checked, the scraper will NOT update the name, description, or brand of this product."
        ),
    )

    created_at = models.DateTimeField(
        _("Created At"),
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        _("Updated At"),
        auto_now=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["brand__name", "name"]

        constraints = [
            models.UniqueConstraint(
                fields=["brand", "name", "weight"], name="unique_product_brand_weight"
            )
        ]

        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["brand", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.brand.name} - {self.name} ({self.weight}g)"


class ProductStore(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name=_("Related Product"),
        related_name="store_links",
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        verbose_name=_("Associated Store"),
    )

    external_id = models.CharField(
        _("Store Product ID"),
        max_length=100,
        help_text=_("Unique identifier in store system (e.g., SKU)"),
        blank=True,
    )

    product_link = models.URLField(
        _("Store Product URL"),
        help_text=_("Direct URL to product page in the store"),
    )

    affiliate_link = models.URLField(
        _("Affiliate Tracking URL"),
        help_text=_("URL with affiliate tracking parameters"),
        blank=True,
        null=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Store Product Link")
        verbose_name_plural = _("Store Product Links")
        ordering = ["store__name", "product__name"]

        constraints = [
            models.UniqueConstraint(
                fields=["product", "store"], name="unique_product_store"
            ),
            models.UniqueConstraint(
                fields=["store", "external_id"],
                name="unique_store_external_id",
                condition=models.Q(external_id__isnull=False)
                & ~models.Q(external_id=""),
            ),
        ]

        indexes = [
            models.Index(fields=["external_id"]),
            models.Index(fields=["store", "product"]),
        ]

    def __str__(self) -> str:
        return f"{self.store.name} -> {self.product.name}"


class ProductPriceHistory(models.Model):
    class StockStatus(models.TextChoices):
        AVAILABLE = "A", _("Available")
        LAST_UNITS = "L", _("Last Units")
        OUT_OF_STOCK = "O", _("Out of Stock")

    store_product_link = models.ForeignKey(
        ProductStore,
        on_delete=models.CASCADE,
        verbose_name=_("Store Product Link"),
        related_name="price_history",
    )

    price = models.DecimalField(
        _("Current Price"),
        max_digits=10,
        decimal_places=2,
    )

    stock_status = models.CharField(
        _("Inventory Status"),
        max_length=1,
        choices=StockStatus.choices,
        default=StockStatus.AVAILABLE,
    )

    collected_at = models.DateTimeField(
        _("Collection Timestamp"),
        auto_now_add=True,
    )

    history = HistoricalRecords(
        verbose_name=_("Version History"),
        excluded_fields=["history"],
    )

    class Meta:
        ordering = ["-collected_at"]
        get_latest_by = "collected_at"
        verbose_name = _("Price Tracking Record")
        verbose_name_plural = _("Price Tracking Records")

        indexes = [
            models.Index(fields=["collected_at"]),
            models.Index(fields=["stock_status"]),
            models.Index(fields=["store_product_link", "collected_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.store_product_link} | R${self.price} @ {self.collected_at:%d/%m %H:%M}"


class NutritionFacts(models.Model):
    description = models.CharField(
        _("Internal Label"),
        max_length=200,
        blank=True,
        help_text=_(
            "E.g. 'Saborizada' or 'Natural' - helps you identify this table in the admin."
        ),
    )

    serving_size_grams = models.PositiveSmallIntegerField(_("Serving Size (g)"))
    energy_kcal = models.PositiveSmallIntegerField(_("Energy (kcal)"))
    proteins = models.DecimalField(_("Proteins (g)"), max_digits=5, decimal_places=1)
    carbohydrates = models.DecimalField(_("Carbs (g)"), max_digits=5, decimal_places=1)
    total_sugars = models.DecimalField(
        _("Total Sugars (g)"), max_digits=5, decimal_places=1, default=0
    )
    added_sugars = models.DecimalField(
        _("Added Sugars (g)"), max_digits=5, decimal_places=1, default=0
    )
    total_fats = models.DecimalField(
        _("Total Fats (g)"), max_digits=5, decimal_places=1
    )
    saturated_fats = models.DecimalField(
        _("Saturated Fats (g)"), max_digits=5, decimal_places=1, default=0
    )
    trans_fats = models.DecimalField(
        _("Trans Fats (g)"), max_digits=5, decimal_places=1, default=0
    )
    dietary_fiber = models.DecimalField(
        _("Dietary Fiber (g)"), max_digits=5, decimal_places=1, default=0
    )
    sodium = models.PositiveIntegerField(_("Sodium (mg)"), default=0)

    class Meta:
        verbose_name = _("Nutrition Facts")
        verbose_name_plural = _("Nutrition Facts")

    def __str__(self) -> str:
        return f"{self.description or 'Generic Nutrition Facts'}"


class Micronutrient(models.Model):
    class Units(models.TextChoices):
        GRAM = "g", "g"
        MILLIGRAM = "mg", "mg"
        MICROGRAM = "mcg", "mcg"
        IU = "IU", "IU"
        PERCENT = "%", "%"

    nutrition_facts = models.ForeignKey(
        NutritionFacts, on_delete=models.CASCADE, related_name="micronutrients"
    )

    name = models.CharField(
        _("Nutrient Name"),
        max_length=100,
        help_text=_("e.g., Vitamin C, Iron"),
    )

    value = models.DecimalField(
        _("Quantity"),
        max_digits=10,
        decimal_places=3,
    )

    unit = models.CharField(
        _("Unit"),
        max_length=10,
        choices=Units.choices,
        default=Units.MILLIGRAM,
    )

    class Meta:
        verbose_name = _("Micronutrient")
        verbose_name_plural = _("Micronutrients")
        constraints = [
            models.UniqueConstraint(
                fields=["nutrition_facts", "name"], name="unique_nutrient_per_facts"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name}: {self.value}{self.unit}"


class ProductNutrition(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name=_("Base Product"),
        related_name="nutrition_profiles",
    )

    nutrition_facts = models.ForeignKey(
        NutritionFacts,
        on_delete=models.CASCADE,
        verbose_name=_("Nutrition Facts"),
        related_name="product_profiles",
    )

    flavors = models.ManyToManyField(
        Flavor,
        verbose_name=_("Flavors"),
        blank=True,
    )

    class Meta:
        verbose_name = _("Product Nutrition Profile")
        verbose_name_plural = _("Product Nutrition Profiles")
        constraints = [
            models.UniqueConstraint(
                fields=["product", "nutrition_facts"],
                name="unique_product_nutrition_facts",
            )
        ]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.nutrition_facts}"
