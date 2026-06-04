"""Core catalog, alert, and pricing models."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from typing import ClassVar, TypedDict

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from common.models import BaseModel

logger = logging.getLogger(__name__)


class MicronutrientHashInput(TypedDict):
    """Typed micronutrient data used for nutrition hash computation."""

    name: str
    value: float
    unit: str


class Brand(BaseModel):
    """Brand definition."""

    name = models.CharField(_("Name"), max_length=100, unique=True)
    display_name = models.CharField(_("Display Name"), max_length=100, unique=True)
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Brand description"),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Brand")
        verbose_name_plural = _("Brands")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return display name."""
        return self.display_name


class Store(BaseModel):
    """Store definition."""

    name = models.CharField(_("Name"), max_length=100, unique=True)
    display_name = models.CharField(_("Display Name"), max_length=100, unique=True)
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Store description"),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Store")
        verbose_name_plural = _("Stores")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return display name."""
        return self.display_name


class Flavor(BaseModel):
    """Flavor definition for nutrition profiles."""

    name = models.CharField(_("Name"), max_length=100, unique=True)
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Flavor description"),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Flavor")
        verbose_name_plural = _("Flavors")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return name."""
        return self.name


class Tag(MP_Node, BaseModel):
    """Hierarchical tag model."""

    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
        help_text=_("Unique tag name"),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Tag description"),
    )

    node_order_by = ("name",)

    class Meta:
        """Meta options."""

        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")

    def __str__(self) -> str:
        """Return name."""
        return self.name


class Category(MP_Node, BaseModel):
    """Hierarchical category model."""

    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
        help_text=_("Unique category name"),
    )

    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Category description"),
    )

    node_order_by = ("name",)

    class Meta:
        """Meta options."""

        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

    def __str__(self) -> str:
        """Return name."""
        return self.name


class Product(BaseModel):
    """Main product model."""

    class Type(models.TextChoices):
        """Product types."""

        SIMPLE = "SIMPLE", _("Simple Product")
        COMBO = "COMBO", _("Combo/Kit")

    class Packaging(models.TextChoices):
        """Packaging types."""

        REFILL = "REFILL", _("Refill Package")
        CONTAINER = "CONTAINER", _("Container Package")
        BAR = "BAR", _("Bar")
        OTHER = "OTHER", _("Other")

    type = models.CharField(
        _("Product Type"),
        max_length=20,
        choices=Type.choices,
        default=Type.SIMPLE,
    )

    name = models.CharField(_("Product Name"), max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, verbose_name=_("Brand"))
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Marketing description"),
    )

    weight = models.PositiveIntegerField(
        _("Weight (grams)"),
        null=True,
        blank=True,
        help_text=_("Total product weight in grams"),
    )

    ean = models.CharField(
        _("EAN/GTIN"),
        max_length=14,
        unique=True,
        null=True,
        blank=True,
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

    stores = models.ManyToManyField(
        Store,
        through="ProductStore",
        verbose_name=_("Available In Stores"),
        blank=True,
    )

    tags = models.ManyToManyField(
        Tag,
        verbose_name=_("Product Tags"),
        blank=True,
    )

    components = models.ManyToManyField(
        "self",
        through="ProductComponent",
        symmetrical=False,
        verbose_name=_("Components"),
        blank=True,
        help_text=_("If this is a Combo, list the products it contains."),
    )

    is_published = models.BooleanField(
        _("Published"),
        default=False,
        help_text=_("If checked, this product will be visible on the public website."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ("brand__name", "name")

        indexes = (
            models.Index(fields=["name"]),
            models.Index(fields=["brand", "name"]),
        )

    def __str__(self) -> str:
        """Return string representation."""
        weight_display = f"{self.weight}g" if self.weight is not None else "No weight"
        return f"{self.brand.display_name} - {self.name} ({weight_display})"

    def save(self, *args: object, **kwargs: object) -> None:
        """Validate rules on save."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate business rules."""
        super().clean()

        if self.ean:
            qs = Product.objects.filter(ean=self.ean)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"ean": _("Product with this EAN already exists.")},
                )


class ProductComponent(BaseModel):
    """Link between a Combo Product (parent) and its components (children)."""

    parent = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="component_links",
        verbose_name=_("Parent Combo"),
    )
    component = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="parent_links",
        verbose_name=_("Component Product"),
    )
    quantity = models.PositiveIntegerField(_("Quantity"), default=1)

    class Meta:
        """Meta options."""

        verbose_name = _("Product Component")
        verbose_name_plural = _("Product Components")
        constraints = (
            models.UniqueConstraint(
                fields=["parent", "component"],
                name="unique_product_component",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.parent.name} -> {self.quantity}x {self.component.name}"


class ProductStore(BaseModel):
    """Curated link between a Product and the merchant Offer that fulfils it.

    The store identity and price series live on the linked :class:`offers.Offer`.
    This model holds only the catalog-side curation: which Store the offer maps
    to and the affiliate tracking URL.
    """

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

    offer = models.OneToOneField(
        "offers.Offer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Merchant Offer"),
        related_name="product_store",
        help_text=_("Merchant offer that holds the price series for this listing"),
    )

    affiliate_link = models.URLField(
        _("Affiliate Tracking URL"),
        max_length=500,
        help_text=_("URL with affiliate tracking parameters"),
        blank=True,
        default="",
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Store Product Link")
        verbose_name_plural = _("Store Product Links")
        ordering = ("store__name", "product__name")

        constraints = (
            models.UniqueConstraint(
                fields=["product", "store"],
                name="unique_product_store",
            ),
        )

        indexes = (models.Index(fields=["store", "product"]),)

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.store.name} -> {self.product.name}"

    @property
    def external_id(self) -> str:
        """Return the merchant identifier from the linked offer."""
        return self.offer.external_id if self.offer else ""

    @property
    def product_link(self) -> str:
        """Return the store product URL from the linked offer."""
        return self.offer.url if self.offer else ""


class NutritionFacts(BaseModel):
    """Nutritional information model."""

    HASH_FIELDS: ClassVar[tuple[str, ...]] = (
        "serving_size_grams",
        "energy_kcal",
        "proteins",
        "carbohydrates",
        "total_sugars",
        "added_sugars",
        "total_fats",
        "saturated_fats",
        "trans_fats",
        "dietary_fiber",
        "sodium",
    )

    description = models.CharField(
        _("Internal Label"),
        max_length=200,
        blank=True,
        help_text=_(
            "E.g. 'Saborizada' or 'Natural' to identify this table in the admin.",
        ),
    )

    serving_size_grams = models.DecimalField(
        _("Serving Size (g)"),
        max_digits=6,
        decimal_places=2,
    )
    energy_kcal = models.PositiveSmallIntegerField(_("Energy (kcal)"))
    proteins = models.DecimalField(_("Proteins (g)"), max_digits=5, decimal_places=1)
    carbohydrates = models.DecimalField(_("Carbs (g)"), max_digits=5, decimal_places=1)
    total_sugars = models.DecimalField(
        _("Total Sugars (g)"),
        max_digits=5,
        decimal_places=1,
        default=0,
    )
    added_sugars = models.DecimalField(
        _("Added Sugars (g)"),
        max_digits=5,
        decimal_places=1,
        default=0,
    )
    total_fats = models.DecimalField(
        _("Total Fats (g)"),
        max_digits=5,
        decimal_places=1,
    )
    saturated_fats = models.DecimalField(
        _("Saturated Fats (g)"),
        max_digits=5,
        decimal_places=1,
        default=0,
    )
    trans_fats = models.DecimalField(
        _("Trans Fats (g)"),
        max_digits=5,
        decimal_places=1,
        default=0,
    )
    dietary_fiber = models.DecimalField(
        _("Dietary Fiber (g)"),
        max_digits=5,
        decimal_places=1,
        default=0,
    )
    sodium = models.DecimalField(
        _("Sodium (mg)"),
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    content_hash = models.CharField(
        _("Content Hash"),
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_(
            "SHA-256 fingerprint of the nutritional values.",
        ),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Nutrition Facts")
        verbose_name_plural = _("Nutrition Facts")

        constraints = (
            models.CheckConstraint(
                condition=models.Q(serving_size_grams__gt=0),
                name="nutrition_facts_positive_serving_size",
            ),
        )

    @classmethod
    def compute_hash(
        cls,
        field_values: dict[str, object],
        *,
        micronutrients: list[MicronutrientHashInput] | None = None,
    ) -> str:
        """Compute a stable SHA-256 from nutritional field values and micronutrients."""
        data: dict[str, object] = {
            field: float(field_values[field]) for field in cls.HASH_FIELDS
        }
        data["micronutrients"] = sorted(
            micronutrients or [],
            key=lambda micronutrient: micronutrient["name"],
        )
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def __str__(self) -> str:
        """Return string representation."""
        short_hash = self.content_hash[:7] if self.content_hash else "-------"
        if self.description:
            return f"{short_hash} — {self.description}"
        return short_hash


class Micronutrient(BaseModel):
    """Micronutrient (vitamin/mineral) definition."""

    class Units(models.TextChoices):
        """Supported units of measurement."""

        UNKNOWN = "-", "-"
        GRAM = "g", "g"
        MILLIGRAM = "mg", "mg"
        MICROGRAM = "mcg", "mcg"
        IU = "IU", "IU"
        PERCENT = "%", "%"

    nutrition_facts = models.ForeignKey(
        NutritionFacts,
        on_delete=models.CASCADE,
        related_name="micronutrients",
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
        default=Units.UNKNOWN,
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Micronutrient")
        verbose_name_plural = _("Micronutrients")
        constraints = (
            models.UniqueConstraint(
                fields=["nutrition_facts", "name"],
                name="unique_nutrient_per_facts",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name}: {self.value}{self.unit}"


class ProductNutrition(BaseModel):
    """Links distinct nutrition profiles to a product."""

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
        """Meta options."""

        verbose_name = _("Product Nutrition Profile")
        verbose_name_plural = _("Product Nutrition Profiles")
        constraints = (
            models.UniqueConstraint(
                fields=["product", "nutrition_facts"],
                name="unique_product_nutrition_facts",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.product.name} - {self.nutrition_facts}"


class AlertSubscriber(BaseModel):
    """Stores email subscriptions for price alerts."""

    email = models.EmailField(_("Email"), unique=True)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Alert Subscriber")
        verbose_name_plural = _("Alert Subscribers")

    def __str__(self) -> str:
        """Return email address."""
        return self.email


class APIKey(BaseModel):
    """API Key for external client access."""

    name = models.CharField(
        _("Client Name"),
        max_length=100,
        help_text=_("Who is this key for?"),
    )
    key = models.CharField(
        _("API Key"),
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        """Meta options."""

        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.name} ({self.key[:8]}...)"

    def save(self, *args: object, **kwargs: object) -> None:
        """Generate key on save if missing."""
        if not self.key:
            self.key = secrets.token_urlsafe(32)
            logger.debug("Generated API key for client: %s", self.name)
        super().save(*args, **kwargs)
