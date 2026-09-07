"""Core catalog, alert, and pricing models."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from decimal import Decimal
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from common.models import BaseModel

from . import units

logger = logging.getLogger(__name__)


def mass_field(label: object, **kwargs: object) -> models.DecimalField:
    """Return a nullable mass column stored in the canonical unit."""
    return models.DecimalField(
        label,
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
        **kwargs,
    )


class Unit(models.TextChoices):
    """Units a nutrition label may state, taken from the unit registry."""

    UNKNOWN = "-", "-"
    GRAM = "g", "g"
    MILLIGRAM = "mg", "mg"
    MICROGRAM = "mcg", "mcg"
    KILOGRAM = "kg", "kg"
    KILOCALORIE = "kcal", "kcal"
    IU = "IU", "IU"
    PERCENT = "%", "%"

    @classmethod
    def normalize(cls, value: str) -> str:
        """Return a supported unit or the unknown fallback."""
        candidate = value.strip()
        return candidate if candidate in cls.values else cls.UNKNOWN


class Active(BaseModel):
    """A substance the catalog can rank and filter products by.

    Protein is one row here, not a privileged column: creatine, caffeine, EPA or
    collagen are described the same way. Macros that the nutrition label carries
    in a dedicated column point at it through ``nutrition_field``; everything
    else is read from :class:`NutritionActive` rows.
    """

    NUTRITION_FIELDS: ClassVar[tuple[str, ...]] = (
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

    name = models.CharField(_("Name"), max_length=100, unique=True)
    slug = models.SlugField(_("Slug"), max_length=100, unique=True)
    display_unit = models.CharField(
        _("Display Unit"),
        max_length=10,
        choices=Unit,
        default=Unit.GRAM,
        help_text=_("Unit this active is presented in; storage stays canonical."),
    )
    nutrition_field = models.CharField(
        _("Nutrition Label Field"),
        max_length=30,
        blank=True,
        default="",
        choices=[(field, field) for field in NUTRITION_FIELDS],
        help_text=_(
            "Scalar nutrition column carrying this active. Leave empty to read "
            "it from the nutrition active rows.",
        ),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Active description"),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Active")
        verbose_name_plural = _("Actives")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return name."""
        return self.name


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

    default_active = models.ForeignKey(
        Active,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_categories",
        verbose_name=_("Default Active"),
        help_text=_("Active this category is ranked by when none is requested."),
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

    net_mass = models.DecimalField(
        _("Net Mass"),
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=_("Net content of the package, stored in the canonical unit."),
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
        mass = (
            None
            if self.net_mass is None
            else units.from_canonical(self.net_mass, units.DISPLAY_MASS_UNIT)
        )
        mass_display = (
            f"{mass:g}{units.DISPLAY_MASS_UNIT}" if mass is not None else "No mass"
        )
        return f"{self.brand.display_name} - {self.name} ({mass_display})"

    def save(self, *args: object, **kwargs: object) -> None:
        """Validate rules on save."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate business rules."""
        super().clean()

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
        "serving_size",
        "energy",
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

    serving_size = models.DecimalField(
        _("Serving Size"),
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
    )
    energy = models.DecimalField(
        _("Energy"),
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
    )
    proteins = mass_field(_("Proteins"))
    carbohydrates = mass_field(_("Carbs"))
    total_sugars = mass_field(_("Total Sugars"), default=0)
    added_sugars = mass_field(_("Added Sugars"), default=0)
    total_fats = mass_field(_("Total Fats"))
    saturated_fats = mass_field(_("Saturated Fats"), default=0)
    trans_fats = mass_field(_("Trans Fats"), default=0)
    dietary_fiber = mass_field(_("Dietary Fiber"), default=0)
    sodium = mass_field(_("Sodium"), default=0)

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
                condition=models.Q(serving_size__gt=0)
                | models.Q(serving_size__isnull=True),
                name="nutrition_facts_positive_serving_size",
            ),
        )

    def save(self, *args: object, **kwargs: object) -> None:
        """Keep the content hash in sync with the stored values on every write.

        The hash is owned by the model: no caller recomputes it. When a
        nutrition active changes it re-saves its parent facts (see
        NutritionActive), which lands back here and refreshes the fingerprint.
        """
        self.content_hash = self._content_hash()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {*update_fields, "content_hash", "updated_at"}
        super().save(*args, **kwargs)
        for profile in self.product_profiles.select_related("product"):
            ProductActive.objects.sync_for(profile.product)

    def _content_hash(self) -> str:
        """Return a stable SHA-256 of the scalar values and saved actives."""
        data: dict[str, object] = {
            field: None if (value := getattr(self, field)) is None else float(value)
            for field in self.HASH_FIELDS
        }
        data["micronutrients"] = (
            sorted(
                (
                    {
                        "name": item.active.name,
                        "value": float(item.amount),
                        "unit": item.declared_unit,
                    }
                    for item in self.actives.select_related("active")
                ),
                key=lambda amount: amount["name"],
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


class NutritionActive(BaseModel):
    """The amount of one :class:`Active` measured in a nutrition label."""

    nutrition_facts = models.ForeignKey(
        NutritionFacts,
        on_delete=models.CASCADE,
        related_name="actives",
    )

    active = models.ForeignKey(
        Active,
        on_delete=models.PROTECT,
        related_name="label_amounts",
        verbose_name=_("Active"),
    )

    amount = models.DecimalField(
        _("Amount"),
        max_digits=16,
        decimal_places=3,
        help_text=_("Stored in the canonical unit of the declared dimension."),
    )

    declared_unit = models.CharField(
        _("Declared Unit"),
        max_length=10,
        choices=Unit,
        default=Unit.UNKNOWN,
        help_text=_("Unit the printed label used, kept so it can be shown again."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Nutrition Active")
        verbose_name_plural = _("Nutrition Actives")
        constraints = (
            models.UniqueConstraint(
                fields=["nutrition_facts", "active"],
                name="unique_nutrient_per_facts",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.active.name}: {self.declared_amount}{self.declared_unit}"

    @property
    def declared_amount(self) -> Decimal | None:
        """Return the amount in the unit the label declared it in."""
        return units.from_canonical(self.amount, self.declared_unit)

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the amount and refresh its parent facts hash."""
        super().save(*args, **kwargs)
        self.nutrition_facts.save(update_fields=["content_hash", "updated_at"])

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Remove the amount and refresh its parent facts hash."""
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

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the link and refresh the product's derived concentrations."""
        super().save(*args, **kwargs)
        ProductActive.objects.sync_for(self.product)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Remove the link and refresh the product's derived concentrations."""
        product = self.product
        result = super().delete(*args, **kwargs)
        ProductActive.objects.sync_for(product)
        return result


class ProductActiveManager(models.Manager):
    """Manager that keeps product concentrations derived from nutrition data."""

    def sync_for(self, product: Product) -> None:
        """Recompute the product's concentrations from its nutrition profiles.

        A product may carry several labels (one per flavor). The catalog ranks
        by the strongest one, so each active keeps its highest concentration
        across the profiles. Rows for actives that no longer appear are dropped.
        """
        fractions = self._fractions(product)

        self.filter(product=product).exclude(active_id__in=fractions).delete()

        for active_id, fraction in fractions.items():
            self.update_or_create(
                product=product,
                active_id=active_id,
                defaults={"fraction": fraction},
            )

    def _fractions(self, product: Product) -> dict[int, Decimal]:
        """Return the highest mass fraction of each active across the labels."""
        actives = list(Active.objects.all())
        highest: dict[int, Decimal] = {}

        profiles = product.nutrition_profiles.select_related(
            "nutrition_facts",
        ).prefetch_related("nutrition_facts__actives")

        for profile in profiles:
            for active_id, value in self._label_fractions(
                profile.nutrition_facts,
                actives,
            ).items():
                if value > highest.get(active_id, Decimal(0)):
                    highest[active_id] = value

        return highest

    def _label_fractions(
        self,
        facts: NutritionFacts,
        actives: list[Active],
    ) -> dict[int, Decimal]:
        """Return the mass fraction of each active in one label.

        Both sides of the ratio are already canonical, so the result is a plain
        dimensionless number and no unit is named anywhere in the arithmetic.
        """
        serving = facts.serving_size
        if not serving:
            return {}

        amounts: dict[int, Decimal] = {}

        for active in actives:
            if not active.nutrition_field:
                continue
            value = getattr(facts, active.nutrition_field)
            if value is not None:
                amounts[active.pk] = Decimal(value) / serving

        for entry in facts.actives.all():
            if units.is_convertible(entry.declared_unit):
                amounts[entry.active_id] = entry.amount / serving

        return amounts


class ProductActive(BaseModel):
    """Mass fraction of one active in a product.

    This is derived from the product's nutrition profiles and is what the public
    catalog ranks, filters and sorts on. The value is dimensionless -- grams of
    active per gram of product, milligrams per milligram, the same number -- so
    every catalog metric is arithmetic over one column, whatever the active is
    and whatever unit the result is later presented in.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="actives",
        verbose_name=_("Product"),
    )

    active = models.ForeignKey(
        Active,
        on_delete=models.CASCADE,
        related_name="product_amounts",
        verbose_name=_("Active"),
    )

    fraction = models.DecimalField(
        _("Mass Fraction"),
        max_digits=12,
        decimal_places=8,
        help_text=_("Mass of the active per unit of product mass."),
    )

    objects = ProductActiveManager()

    class Meta:
        """Meta options."""

        verbose_name = _("Product Active")
        verbose_name_plural = _("Product Actives")
        ordering = ("product__name", "active__name")
        constraints = (
            models.UniqueConstraint(
                fields=["product", "active"],
                name="unique_product_active",
            ),
        )
        indexes = (models.Index(fields=["active", "fraction"]),)

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.product.name} - {self.active.name}: {self.fraction}"


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
