"""Core catalog, alert, and pricing models."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from common.models import BaseModel

logger = logging.getLogger(__name__)


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
    """Main product model.

    ``kind`` is the structural discriminator: a ``COMBO`` is assembled from other
    products through :class:`ProductComponent`, and a ``SIMPLE`` product never
    has components. It is orthogonal to :class:`Category`, which describes what
    the product *is*.
    """

    class Kind(models.TextChoices):
        """Structural product kinds."""

        SIMPLE = "SIMPLE", _("Simple Product")
        COMBO = "COMBO", _("Combo")

    class Packaging(models.TextChoices):
        """Packaging types."""

        REFILL = "REFILL", _("Refill Package")
        CONTAINER = "CONTAINER", _("Container Package")
        BAR = "BAR", _("Bar")
        OTHER = "OTHER", _("Other")

    name = models.CharField(_("Product Name"), max_length=200)
    kind = models.CharField(
        _("Kind"),
        max_length=10,
        choices=Kind.choices,
        default=Kind.SIMPLE,
        help_text=_("Combos are assembled from other catalog products."),
    )
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
            models.Index(fields=["kind"]),
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

        # A blank form field arrives as "", which the unique index treats as a
        # real value: the second product without an EAN would collide with it.
        if not self.ean:
            self.ean = None

        if self.ean:
            qs = Product.objects.filter(ean=self.ean)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {"ean": _("Product with this EAN already exists.")},
                )

        if self.kind == self.Kind.SIMPLE and self.pk and self.component_links.exists():
            raise ValidationError(
                {"kind": _("A product with components must be a combo.")},
            )

    @property
    def is_combo(self) -> bool:
        """Return whether this product is assembled from other products."""
        return self.kind == self.Kind.COMBO


class ProductComponent(BaseModel):
    """One item inside a combo product."""

    parent = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="component_links",
        verbose_name=_("Combo"),
    )
    component = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="parent_links",
        verbose_name=_("Component"),
    )
    quantity = models.PositiveIntegerField(_("Quantity"), default=1)

    class Meta:
        """Meta options."""

        verbose_name = _("Component")
        verbose_name_plural = _("Components")
        constraints = (
            models.UniqueConstraint(
                fields=["parent", "component"],
                name="unique_product_component",
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("component")),
                name="product_component_not_self",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.quantity}x {self.component.name}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Validate rules on save."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Reject self-references, combo nesting, and simple-product parents."""
        super().clean()

        parent = self.parent if self.parent_id else None
        component = self.component if self.component_id else None

        if parent and component and parent.pk == component.pk:
            raise ValidationError(
                {"component": _("A product cannot be a component of itself.")},
            )

        # Components are always simple products, so the assembly is one level
        # deep by construction: no cycle can be built and no recursion is needed
        # to resolve a combo into the products it contains.
        if component and component.is_combo:
            raise ValidationError(
                {"component": _("A combo cannot be used as a component.")},
            )

        if parent and not parent.is_combo:
            raise ValidationError(
                {"parent": _("Only combos can have components.")},
            )


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

    # Extraction rarely recovers every value of a label, and an unknown value is
    # not zero: the scalar macros stay nullable so a partial table can be staged
    # and completed later without inventing numbers.
    serving_size_grams = models.DecimalField(
        _("Serving Size (g)"),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    energy_kcal = models.PositiveSmallIntegerField(
        _("Energy (kcal)"),
        null=True,
        blank=True,
    )
    proteins = models.DecimalField(
        _("Proteins (g)"),
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )
    carbohydrates = models.DecimalField(
        _("Carbs (g)"),
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )
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
        null=True,
        blank=True,
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
        editable=False,
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
                condition=models.Q(serving_size_grams__gt=0)
                | models.Q(serving_size_grams__isnull=True),
                name="nutrition_facts_positive_serving_size",
            ),
        )

    def save(self, *args: object, **kwargs: object) -> None:
        """Keep the content hash in sync with the stored values on every write.

        The hash is owned by the model: no caller recomputes it. When a
        micronutrient changes it re-saves its parent facts (see Micronutrient),
        which lands back here and refreshes the fingerprint.
        """
        self.content_hash = self._content_hash()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {*update_fields, "content_hash", "updated_at"}
        super().save(*args, **kwargs)

    def _content_hash(self) -> str:
        """Return a stable SHA-256 of the scalar values and saved micronutrients."""
        data: dict[str, object] = {
            field: None if (value := getattr(self, field)) is None else float(value)
            for field in self.HASH_FIELDS
        }
        data["micronutrients"] = (
            sorted(
                (
                    {"name": item.name, "value": float(item.value), "unit": item.unit}
                    for item in self.micronutrients.all()
                ),
                key=lambda micronutrient: micronutrient["name"],
            )
            if self.pk
            else []
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

        @classmethod
        def normalize(cls, value: str) -> str:
            """Return a supported unit or the unknown fallback."""
            candidate = value.strip()
            return candidate if candidate in cls.values else cls.UNKNOWN

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

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the micronutrient and refresh its parent facts hash."""
        super().save(*args, **kwargs)
        self.nutrition_facts.save(update_fields=["content_hash", "updated_at"])

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Remove the micronutrient and refresh its parent facts hash."""
        facts = self.nutrition_facts
        result = super().delete(*args, **kwargs)
        facts.save(update_fields=["content_hash", "updated_at"])
        return result


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
