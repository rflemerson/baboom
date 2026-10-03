"""Offers: one seller's buyable proposal for one unit, and its price history.

``store_slug`` and ``external_id`` are the legacy identity, kept as an alias
until every reader uses the listing, variant and seller account.
"""

from __future__ import annotations

import unicodedata

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


class StockStatus(models.TextChoices):
    """Canonical stock availability status for the pricing domain."""

    AVAILABLE = "A", _("Available")
    LAST_UNITS = "L", _("Last Units")
    OUT_OF_STOCK = "O", _("Out of Stock")

    @classmethod
    def normalize(cls, value: str) -> str:
        """Return a supported stock status or the available fallback."""
        return value if value in cls.values else cls.AVAILABLE

    @classmethod
    def purchasable(cls) -> tuple[str, ...]:
        """Return the states a buyer can order now; a new state starts outside."""
        return (cls.AVAILABLE, cls.LAST_UNITS)


FLAVOR_OPTION_PREFIXES = ("sabor", "flavor")


def fold(text: str) -> str:
    """Return text compared the way a label is read: no case, accents or gaps."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.casefold().split())


class ItemCondition(models.TextChoices):
    """The state of the item a seller offers."""

    NEW = "new", _("New")
    USED = "used", _("Used")
    REFURBISHED = "refurbished", _("Refurbished")
    UNKNOWN = "unknown", _("Unknown")


class DelistReason(models.TextChoices):
    """Why an offer stopped being a unit the catalog can price."""

    GONE = "gone", _("The store stopped publishing it")
    SUPERSEDED = "superseded", _("Replaced by offers for each buyable variant")


class Offer(BaseModel):
    """One seller's proposal for one buyable unit.

    The offer exists from the moment the scraper first sees it, independent of
    whether it has been linked to a canonical catalog product. It holds the
    latest observed snapshot; the full price series lives in
    :class:`PriceObservation`. Its identity is the listing variant, the seller
    account, the item condition and the fulfillment profile; the store slug
    and external id remain as the legacy alias.
    """

    store_slug = models.CharField(
        _("Store Slug"),
        max_length=100,
        db_index=True,
        help_text=_("Raw store identifier as seen by the scraper"),
    )
    external_id = models.CharField(
        _("Store Product ID"),
        max_length=100,
        db_index=True,
        help_text=_("Unique identifier in the store system (e.g., SKU)"),
    )

    name = models.CharField(
        _("Name"),
        max_length=255,
        blank=True,
        help_text=_("Product name as seen at the store"),
    )
    category = models.CharField(
        _("Category"),
        max_length=255,
        blank=True,
        help_text=_("Category/department as seen at the store"),
    )
    url = models.URLField(
        _("Product URL"),
        max_length=500,
        blank=True,
        help_text=_("Direct URL to the product page at the store"),
    )

    ean = models.CharField(
        _("EAN/GTIN"),
        max_length=14,
        blank=True,
        db_index=True,
        help_text=_("EAN/GTIN observed at the store, used for resolution"),
    )
    sku = models.CharField(
        _("SKU"),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_("SKU observed at the store"),
    )
    pid = models.CharField(
        _("Product ID"),
        max_length=100,
        blank=True,
        help_text=_("Internal product id observed at the store"),
    )

    current_price = models.DecimalField(
        _("Current Price"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Latest observed price"),
    )
    current_stock_status = models.CharField(
        _("Current Stock Status"),
        max_length=1,
        choices=StockStatus,
        default=StockStatus.AVAILABLE,
    )
    current_stock_quantity = models.IntegerField(
        _("Current Stock Quantity"),
        null=True,
        blank=True,
        help_text=_("Latest observed quantity in stock"),
    )

    # "The store stopped listing this unit" and "the store says it is out of
    # stock" are different facts. Stock is a reading; delisting is an absence,
    # and only a complete reading of the unit's own page can establish it.
    last_seen_at = models.DateTimeField(
        _("Last Seen At"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("When the store last published this unit"),
    )
    delisted_at = models.DateTimeField(
        _("Delisted At"),
        null=True,
        blank=True,
        help_text=_("When the unit stopped appearing on a page that did list it"),
    )

    delisted_reason = models.CharField(
        _("Delisted Reason"),
        max_length=20,
        choices=DelistReason,
        blank=True,
        default="",
    )

    missed_runs = models.PositiveIntegerField(
        _("Missed Runs"),
        default=0,
        help_text=_("Consecutive successful store runs that did not publish this unit"),
    )

    options = models.JSONField(
        _("Options"),
        default=list,
        blank=True,
        help_text=_(
            "Options the store published for this unit, verbatim: "
            'a list of {"name", "value"} such as {"name": "Sabor", '
            '"value": "Chocolate"}.',
        ),
    )

    listing_variant = models.ForeignKey(
        "offers.ListingVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="offers",
        verbose_name=_("Listing Variant"),
    )
    seller_account = models.ForeignKey(
        "commerce.SellerAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="offers",
        verbose_name=_("Seller Account"),
        help_text=_("Empty while the source has not said who sells it."),
    )
    fulfillment_profile = models.ForeignKey(
        "commerce.FulfillmentProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="offers",
        verbose_name=_("Fulfillment Profile"),
    )
    item_condition = models.CharField(
        _("Item Condition"),
        max_length=12,
        choices=ItemCondition,
        default=ItemCondition.UNKNOWN,
    )

    @property
    def is_listed(self) -> bool:
        """Whether the store still publishes this unit."""
        return self.delisted_at is None

    @property
    def flavors(self) -> list[str]:
        """Return the flavor values the store published for this unit.

        Stores name the option freely ("Sabor", "Sabor Whey", "Sabores") and a
        kit publishes one per item ("Sabor 2"), so every option whose name
        starts with a flavor word counts, verbatim.
        """
        return [
            str(option["value"])
            for option in self.options or []
            if isinstance(option, dict)
            and option.get("value")
            and fold(str(option.get("name", ""))).startswith(FLAVOR_OPTION_PREFIXES)
        ]

    class Meta:
        """Meta options."""

        verbose_name = _("Offer")
        verbose_name_plural = _("Offers")
        ordering = ("store_slug", "external_id")
        constraints = (
            models.UniqueConstraint(
                fields=["store_slug", "external_id"],
                name="unique_offer_identity",
            ),
        )
        indexes = (models.Index(fields=["store_slug", "external_id"]),)

    def __str__(self) -> str:
        """Name the offer the way a curator tells the store's units apart."""
        parts = [f"[{self.store_slug}] {self.name or self.external_id}"]
        if flavors := self.flavors:
            parts.append(", ".join(flavors))
        parts.append(
            f"R$ {self.current_price}"
            if self.current_price is not None
            else "no price",
        )
        if not self.is_listed:
            parts.append("delisted")
        return f"{' — '.join(parts)} (#{self.external_id})"


class PriceObservation(BaseModel):
    """An append-only price/stock snapshot for an offer at a point in time."""

    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name="price_observations",
        verbose_name=_("Offer"),
    )
    price = models.DecimalField(
        _("Price"),
        max_digits=10,
        decimal_places=2,
    )
    stock_status = models.CharField(
        _("Stock Status"),
        max_length=1,
        choices=StockStatus,
        default=StockStatus.AVAILABLE,
    )
    observed_at = models.DateTimeField(
        _("Observed At"),
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Price Observation")
        verbose_name_plural = _("Price Observations")
        ordering = ("-observed_at",)
        get_latest_by = "observed_at"
        indexes = (
            models.Index(fields=["offer", "-observed_at"]),
            models.Index(fields=["stock_status"]),
        )

    def __str__(self) -> str:
        """Return string representation."""
        observed_at = self.observed_at.strftime("%d/%m %H:%M")
        return f"{self.offer} | R${self.price} @ {observed_at}"
