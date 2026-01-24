import hashlib
import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords
from treebeard.mp_tree import MP_Node

logger = logging.getLogger(__name__)


class BaseModel(models.Model):
    created_at = models.DateTimeField(
        _("Created At"),
        db_index=True,
        default=timezone.now,
    )
    updated_at = models.DateTimeField(
        _("Updated At"),
        auto_now=True,
    )

    class Meta:
        abstract = True


class Brand(BaseModel):
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


class Store(BaseModel):
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


class Flavor(BaseModel):
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


class Tag(MP_Node, BaseModel):  # type: ignore[django-manager-missing]
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


class Category(MP_Node, BaseModel):  # type: ignore[django-manager-missing]
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


class Product(BaseModel):
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

    is_published = models.BooleanField(
        _("Published"),
        default=False,
        help_text=_("If checked, this product will be visible on the public website."),
    )

    last_enriched_at = models.DateTimeField(
        _("Last Enriched By LLM"),
        null=True,
        blank=True,
        help_text=_("Timestamp of last content update by LLM agent"),
    )

    # Product change history
    history = HistoricalRecords()

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

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        # 1. Validate EAN uniqueness (excluding self)
        if self.ean:
            qs = Product.objects.filter(ean=self.ean)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"ean": _("Product with this EAN already exists.")}
                )

        # 2. Validate Brand + Name + Weight uniqueness (excluding self)
        if self.brand_id and self.name and self.weight:
            qs = Product.objects.filter(
                brand_id=self.brand_id, name=self.name, weight=self.weight
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    _("Product with this brand, name, and weight already exists.")
                )


class ProductStore(BaseModel):
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


class NutritionFacts(BaseModel):
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
    sodium = models.DecimalField(
        _("Sodium (mg)"), max_digits=10, decimal_places=2, default=0
    )

    content_hash = models.CharField(
        _("Content Hash"),
        max_length=64,
        unique=True,
        db_index=True,
        blank=True,
        help_text=_("Auto-computed hash of nutritional values for deduplication"),
    )

    class Meta:
        verbose_name = _("Nutrition Facts")
        verbose_name_plural = _("Nutrition Facts")

    def __str__(self) -> str:
        return f"{self.description or 'Generic Nutrition Facts'}"

    def save(self, *args, **kwargs):
        # Automatically generate hash using centralized logic.
        # If micronutrients are not passed (e.g. admin), generate hash only from macros.
        if not self.content_hash:
            self.content_hash = self.generate_hash(source=self)
        super().save(*args, **kwargs)

    @classmethod
    def generate_hash(
        cls, source: Any, micronutrients: list[dict[str, Any]] | None = None
    ) -> str:
        """
        Single Source of Truth for Nutritional Hashing.
        Generates deterministic hash based on Macros and (optionally) Micros.

        Args:
            source: Can be a NutritionFacts instance OR a dictionary (from Service).
            micronutrients: List of dictionaries [{'name': '...', 'value': ...}, ...].
                            Required if 'source' is dict, or to complement the hash.
        """

        # 1. Strict formatting function (Resolves 24 vs 24.00)
        def fmt(val: Any) -> str:
            try:
                # Convert to float first to handle decimals/strings
                # Format with 2 fixed decimal places
                return f"{float(val):.2f}"
            except (ValueError, TypeError):
                return "0.00"

        # 2. Helper to extract value whether it is Dict or Object
        def get_val(key: str) -> Any:
            if isinstance(source, dict):
                return source.get(key)
            return getattr(source, key, None)

        # 3. Macro List (Order matters!)
        parts = [
            fmt(get_val("serving_size_grams")),
            fmt(get_val("energy_kcal")),
            fmt(get_val("proteins")),
            fmt(get_val("carbohydrates")),
            fmt(get_val("total_sugars")),
            fmt(get_val("added_sugars")),
            fmt(get_val("total_fats")),
            fmt(get_val("saturated_fats")),
            fmt(get_val("trans_fats")),
            fmt(get_val("dietary_fiber")),
            fmt(get_val("sodium")),
        ]

        # 4. Add Micronutrients (if provided)
        if micronutrients:
            # Sort by name to ensure determinism
            micros_sorted = sorted(micronutrients, key=lambda x: x["name"])
            for m in micros_sorted:
                # Supports both dict and Micronutrient object (future case)
                name = m.get("name") if isinstance(m, dict) else m.name
                val = m.get("value") if isinstance(m, dict) else m.value
                unit = m.get("unit", "mg") if isinstance(m, dict) else m.unit

                parts.append(f"{name}:{fmt(val)}:{unit}")

        raw_string = "|".join(parts)
        return hashlib.sha256(raw_string.encode()).hexdigest()


class Micronutrient(BaseModel):
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


class ProductNutrition(BaseModel):
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


class AlertSubscriber(BaseModel):
    """Stores email subscriptions for price alerts."""

    email = models.EmailField(_("Email"), unique=True)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Alert Subscriber")
        verbose_name_plural = _("Alert Subscribers")

    def __str__(self) -> str:
        return self.email
