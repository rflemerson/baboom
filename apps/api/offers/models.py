"""Offer layer: merchant listings and their price observations.

This app is the neutral kernel of the pricing domain. It depends only on
``common`` and is referenced by both ``scrapers`` (which writes offers) and
``core`` (which links canonical products to offers). It must never import from
either of those apps, so store identity is kept as a raw ``store_slug`` string
and resolved to a curated ``core.Store`` at the boundary.
"""

from __future__ import annotations

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


class Offer(BaseModel):
    """A product-for-sale at a specific merchant, identified by store + id.

    The offer exists from the moment the scraper first sees it, independent of
    whether it has been linked to a canonical catalog product. It holds the
    latest observed snapshot; the full price series lives in
    :class:`PriceObservation`.
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
        """Return string representation."""
        return f"[{self.store_slug}] {self.external_id}"


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
