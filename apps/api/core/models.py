"""Core catalog, alert, and pricing models."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from common.models import BaseModel
from offers.models import fold

from . import units


def label_field(
    label: object,
    unit: str,
    *,
    max_digits: int = 16,
    **kwargs: object,
) -> models.DecimalField:
    """Return a nullable column holding a value as the label prints it.

    The unit is part of the field's name and help text, so every surface that
    renders the field -- admin, form spec, MCP -- tells the curator what to type.
    """
    return models.DecimalField(
        format_lazy("{} ({})", label, unit),
        max_digits=max_digits,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=format_lazy(
            "{} {}.",
            _("As printed on the label, in"),
            unit,
        ),
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
    scraper_slug = models.SlugField(
        _("Scraper Slug"),
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text=_(
            "The store_slug the scraper records on this store's offers. "
            "Empty for a store nothing scrapes.",
        ),
    )
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
        """Name the category by its whole path, as a curator places it."""
        return " > ".join(node.name for node in [*self.get_ancestors(), self])


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

    net_mass = label_field(_("Net Mass"), units.MASS_UNIT)

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
        mass_display = (
            f"{self.net_mass:g}{units.MASS_UNIT}"
            if self.net_mass is not None
            else "No mass"
        )
        return f"{self.brand.display_name} - {self.name} ({mass_display})"

    def save(self, *args: object, **kwargs: object) -> None:
        """Validate rules on save, and refresh the combos this product is part of."""
        self.full_clean()
        super().save(*args, **kwargs)
        if not self.is_combo and self.parent_links.exists():
            ComboActive.objects.sync_parents_of(self)

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
    # PositiveIntegerField allows zero, and zero of a product is not part of a
    # combo: it would divide the combo's price by a mass nobody buys.
    quantity = models.PositiveIntegerField(
        _("Quantity"),
        default=1,
        validators=[MinValueValidator(1)],
    )

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
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="product_component_quantity_positive",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.quantity}x {self.component.name}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Validate rules on save and refresh the combo's active totals."""
        self.full_clean()
        super().save(*args, **kwargs)
        ComboActive.objects.sync_for(self.parent)

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
    """Curated link between a catalog row and the merchant offer that prices it.

    A simple product is ranked once per nutrition profile, and a store sells one
    flavor per offer, so the link names the profile whose label that flavor
    prints: the flavor the store states must be one the label lists. A combo
    ranks through its components and has no label, so it links without one.

    The store is whichever one sells the offer. It is resolved from the offer's
    scraper slug on every save and cannot be chosen, so a link can never show
    one store's name next to another store's price.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name=_("Related Product"),
        related_name="store_links",
    )

    nutrition_profile = models.ForeignKey(
        "ProductNutrition",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Nutrition Profile"),
        related_name="store_links",
        help_text=_(
            "The product's label that this offer's flavor prints. Required for "
            "a simple product, empty for a combo.",
        ),
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        verbose_name=_("Associated Store"),
        editable=False,
        help_text=_("Resolved from the offer; never chosen."),
    )

    offer = models.OneToOneField(
        "offers.Offer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Merchant Offer"),
        related_name="product_store",
        help_text=_(
            "The captured offer that prices this row. Its price, stock, URL and "
            "flavor come from the scraper; nothing about it is typed here.",
        ),
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

        indexes = (models.Index(fields=["store", "product"]),)

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.store.name} -> {self.product.name}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Validate the link and resolve its store before every write."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Resolve the store and reject a link that would misprice a row."""
        super().clean()
        errors: dict[str, list[str]] = {}
        if self.offer_id is None:
            errors.setdefault("offer", []).append(
                str(_("Link a captured offer.")),
            )
        else:
            self._resolve_store(errors)
        if self.product_id is not None:
            self._validate_profile(errors)
        if not errors and self.offer_id is not None:
            self._validate_flavor(errors)
        if errors:
            raise ValidationError(errors)

    def _resolve_store(self, errors: dict[str, list[str]]) -> None:
        """Set the store that sells the offer, or report that none is mapped."""
        offer = self.offer
        if not offer.is_listed:
            errors.setdefault("offer", []).append(
                str(_("The store no longer publishes this offer.")),
            )
        store = Store.objects.filter(scraper_slug=offer.store_slug).first()
        if store is None:
            errors.setdefault("offer", []).append(
                format_lazy(
                    "{} {}.",
                    _("No store is mapped to the scraper slug"),
                    offer.store_slug,
                ),
            )
            return
        self.store = store

    def _validate_profile(self, errors: dict[str, list[str]]) -> None:
        """Require the product's own label on a simple product, none on a combo."""
        profile = self.nutrition_profile
        if self.product.is_combo:
            if profile is not None:
                errors.setdefault("nutrition_profile", []).append(
                    str(_("A combo ranks through its components; leave it empty.")),
                )
            return
        if profile is None:
            errors.setdefault("nutrition_profile", []).append(
                str(_("Choose the product's label that this offer's flavor prints.")),
            )
        elif profile.product_id != self.product_id:
            errors.setdefault("nutrition_profile", []).append(
                str(_("This label belongs to another product.")),
            )

    def _validate_flavor(self, errors: dict[str, list[str]]) -> None:
        """Require the flavor the offer states to be one its label lists."""
        if self.product.is_combo:
            return
        sold = self.offer.flavors
        printed = [flavor.name for flavor in self.nutrition_profile.flavors.all()]
        sold_folded = {fold(flavor) for flavor in sold}
        printed_folded = {fold(flavor) for flavor in printed}
        if len(sold_folded) > 1:
            message = format_lazy(
                "{} {}.",
                _("This offer sells several flavors, so it is a kit:"),
                ", ".join(sold),
            )
        elif printed_folded and not sold_folded:
            message = format_lazy(
                "{} {}.",
                _(
                    "This offer states no flavor, so it cannot price the label "
                    "printed by",
                ),
                ", ".join(printed),
            )
        elif sold_folded - printed_folded:
            message = format_lazy(
                "{} {}; {} {}. {}",
                _("This offer sells"),
                ", ".join(sold),
                _("the chosen label lists"),
                ", ".join(printed) or _("no flavor"),
                _(
                    "Link it to the label of that flavor, or add the flavor to "
                    "this label if the package prints the same table for it.",
                ),
            )
        else:
            return
        errors.setdefault("offer", []).append(str(message))

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

    # The unit each column is printed in on a Brazilian label (RDC 429/2020).
    LABEL_UNITS: ClassVar[dict[str, str]] = {
        "serving_size": "g",
        "energy": "kcal",
        "proteins": "g",
        "carbohydrates": "g",
        "total_sugars": "g",
        "added_sugars": "g",
        "total_fats": "g",
        "saturated_fats": "g",
        "trans_fats": "g",
        "dietary_fiber": "g",
        "sodium": "mg",
    }

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
            "E.g. 'Flavored' or 'Natural' to identify this table in the admin.",
        ),
    )

    serving_size = label_field(_("Serving Size"), LABEL_UNITS["serving_size"])
    energy = label_field(_("Energy"), LABEL_UNITS["energy"], max_digits=10)
    proteins = label_field(_("Proteins"), LABEL_UNITS["proteins"])
    carbohydrates = label_field(_("Carbs"), LABEL_UNITS["carbohydrates"])
    total_sugars = label_field(
        _("Total Sugars"),
        LABEL_UNITS["total_sugars"],
        default=0,
    )
    added_sugars = label_field(
        _("Added Sugars"),
        LABEL_UNITS["added_sugars"],
        default=0,
    )
    total_fats = label_field(_("Total Fats"), LABEL_UNITS["total_fats"])
    saturated_fats = label_field(
        _("Saturated Fats"),
        LABEL_UNITS["saturated_fats"],
        default=0,
    )
    trans_fats = label_field(_("Trans Fats"), LABEL_UNITS["trans_fats"], default=0)
    dietary_fiber = label_field(
        _("Dietary Fiber"),
        LABEL_UNITS["dietary_fiber"],
        default=0,
    )
    sodium = label_field(_("Sodium"), LABEL_UNITS["sodium"], default=0)

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
        help_text=_("As printed on the label, in the declared unit."),
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
        return f"{self.active.name}: {self.amount}{self.declared_unit}"

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
        """Name the label by the product and the flavors that print it."""
        flavors = (
            ", ".join(flavor.name for flavor in self.flavors.all()) if self.pk else ""
        )
        return (
            f"{self.product.name} — {flavors or 'no flavor listed'} "
            f"({self.nutrition_facts})"
        )

    def save(self, *args: object, **kwargs: object) -> None:
        """Persist the link and refresh the product's derived concentrations."""
        super().save(*args, **kwargs)
        ProductActive.objects.sync_for(self.product)


class ProductActiveManager(models.Manager):
    """Manager that keeps product concentrations derived from nutrition data."""

    @transaction.atomic
    def sync_for(self, product: Product) -> None:
        """Refresh concentrations independently for each nutritional profile."""
        Product.objects.select_for_update().get(pk=product.pk)
        actives = list(Active.objects.all())
        profiles = product.nutrition_profiles.select_related(
            "nutrition_facts",
        ).prefetch_related("nutrition_facts__actives")
        for profile in profiles:
            fractions = self._label_fractions(profile.nutrition_facts, actives)
            self.filter(nutrition_profile=profile).exclude(
                active_id__in=fractions,
            ).delete()
            for active_id, fraction in fractions.items():
                self.update_or_create(
                    nutrition_profile=profile,
                    active_id=active_id,
                    defaults={"fraction": fraction},
                )
        ComboActive.objects.sync_parents_of(product)

    def _label_fractions(
        self,
        facts: NutritionFacts,
        actives: list[Active],
    ) -> dict[int, Decimal]:
        """Return the mass fraction of each active in one label.

        Each side is read in the unit its label prints and brought to grams
        here, so the result is a plain dimensionless number.
        """
        serving = self._in_grams(facts.serving_size, facts.LABEL_UNITS["serving_size"])
        if not serving:
            return {}

        amounts: dict[int, Decimal] = {}

        for active in actives:
            if not active.nutrition_field:
                continue
            value = self._in_grams(
                getattr(facts, active.nutrition_field),
                facts.LABEL_UNITS[active.nutrition_field],
            )
            if value is not None:
                amounts[active.pk] = value / serving

        for entry in facts.actives.all():
            value = self._in_grams(entry.amount, entry.declared_unit)
            if value is not None:
                amounts[entry.active_id] = value / serving

        return amounts

    @staticmethod
    def _in_grams(value: Decimal | None, unit: str) -> Decimal | None:
        """Return a printed value in grams, or None when it has no mass."""
        if value is None:
            return None
        return units.to_canonical(Decimal(value), unit)


class ProductActive(BaseModel):
    """Mass fraction of one active in one product nutrition profile.

    Each row comes from exactly one nutrition table and is what the public
    catalog ranks, filters and sorts on. The value is dimensionless -- grams of
    active per gram of product, milligrams per milligram, the same number -- so
    every catalog metric is arithmetic over one column, whatever the active is
    and whatever unit the result is later presented in.
    """

    nutrition_profile = models.ForeignKey(
        ProductNutrition,
        on_delete=models.CASCADE,
        related_name="actives",
        verbose_name=_("Nutrition Profile"),
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
        ordering = (
            "nutrition_profile__product__name",
            "nutrition_profile_id",
            "active__name",
        )
        constraints = (
            models.UniqueConstraint(
                fields=["nutrition_profile", "active"],
                name="unique_profile_active",
            ),
        )
        indexes = (models.Index(fields=["active", "fraction"]),)

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.nutrition_profile} - {self.active.name}: {self.fraction}"


class ComboActiveManager(models.Manager):
    """Manager that keeps combo active totals derived from their components."""

    @transaction.atomic
    def sync_for(self, combo: Product) -> None:
        """Rebuild one combo's active totals from its current components."""
        totals = (
            self._totals(list(combo.component_links.select_related("component")))
            if combo.is_combo
            else {}
        )
        self.filter(combo=combo).exclude(active_id__in=totals).delete()
        for active_id, total_mass in totals.items():
            self.update_or_create(
                combo=combo,
                active_id=active_id,
                defaults={"total_mass": total_mass},
            )

    def sync_parents_of(self, component: Product) -> None:
        """Rebuild every combo the given product is a component of."""
        combos = Product.objects.filter(component_links__component=component)
        for combo in combos.distinct():
            self.sync_for(combo)

    def _totals(self, links: list[ProductComponent]) -> dict[int, Decimal]:
        """Sum each active over the components, if every component has it.

        A component's mass of an active is its quantity times its net mass
        times its smallest fraction across nutrition labels: flavors differ and
        a combo does not say which one it ships, so the figure never overstates
        what the buyer gets. A component that lacks the active on any label, or
        has no net mass, leaves the combo without that active.
        """
        if not links:
            return {}
        per_component: list[dict[int, Decimal]] = []
        for link in links:
            masses = self._component_masses(link)
            if not masses:
                return {}
            per_component.append(masses)
        shared = set.intersection(*(set(masses) for masses in per_component))
        return {
            active_id: sum(
                (masses[active_id] for masses in per_component),
                Decimal(0),
            ).quantize(Decimal("0.001"))
            for active_id in shared
        }

    def _component_masses(self, link: ProductComponent) -> dict[int, Decimal]:
        """Return the mass of each active one component line contributes."""
        component = link.component
        profile_count = component.nutrition_profiles.count()
        if component.net_mass is None or not profile_count:
            return {}
        fractions: dict[int, list[Decimal]] = {}
        rows = ProductActive.objects.filter(
            nutrition_profile__product=component,
        ).values_list("active_id", "fraction")
        for active_id, fraction in rows:
            fractions.setdefault(active_id, []).append(fraction)
        return {
            active_id: link.quantity * component.net_mass * min(values)
            for active_id, values in fractions.items()
            if len(values) == profile_count
        }


class ComboActive(BaseModel):
    """Mass of one active in a whole combo, summed from its components.

    A combo has no nutrition label of its own, so it cannot have a
    :class:`ProductActive` fraction. Its price buys every component and the
    store does not split it, so a row exists only when every component contains
    the active: a price per gram charged against part of what was paid for would
    mislead the ranking.
    """

    combo = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="combo_actives",
        verbose_name=_("Combo"),
    )
    active = models.ForeignKey(
        Active,
        on_delete=models.CASCADE,
        related_name="combo_amounts",
        verbose_name=_("Active"),
    )
    total_mass = models.DecimalField(
        _("Total Mass"),
        max_digits=16,
        decimal_places=3,
        help_text=_(
            "Mass of the active across every component, in the canonical unit."
        ),
    )

    objects = ComboActiveManager()

    class Meta:
        """Meta options."""

        verbose_name = _("Combo Active")
        verbose_name_plural = _("Combo Actives")
        constraints = (
            models.UniqueConstraint(
                fields=["combo", "active"],
                name="unique_combo_active",
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.combo.name} - {self.active.name}: {self.total_mass}"


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
