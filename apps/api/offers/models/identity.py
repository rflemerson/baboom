"""Where an offer is published and the names sources give it.

A listing is the page or advertisement a market publishes; a listing variant
is the unit a buyer selects on it; an offer is one seller's proposal for that
unit. None of them is the catalog product: a channel's own catalog id (an
ASIN, a catalog product) is evidence for curation, never a merge.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


class Listing(BaseModel):
    """A page or advertisement a market publishes."""

    market = models.ForeignKey(
        "commerce.Market",
        on_delete=models.PROTECT,
        related_name="listings",
        verbose_name=_("Market"),
    )
    external_id = models.CharField(
        _("External ID"),
        max_length=100,
        help_text=_("The product or advertisement id the market publishes."),
    )
    url = models.URLField(_("URL"), max_length=500, blank=True)
    title = models.CharField(_("Title"), max_length=255, blank=True)
    catalog_product_id = models.CharField(
        _("Channel catalog ID"),
        max_length=100,
        blank=True,
        help_text=_("The channel's own catalog id, such as an ASIN."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Listing")
        verbose_name_plural = _("Listings")
        ordering = ("market", "external_id")
        constraints = (
            models.UniqueConstraint(
                fields=("market", "external_id"),
                name="unique_listing_per_market",
            ),
        )

    def __str__(self) -> str:
        """Return the title and id."""
        return f"{self.title or self.external_id} ({self.market.namespace})"


class ListingVariant(BaseModel):
    """The unit a buyer selects on a listing: a flavor, a size, a pack."""

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name=_("Listing"),
    )
    external_id = models.CharField(_("External ID"), max_length=100)
    options = models.JSONField(
        _("Options"),
        default=list,
        blank=True,
        help_text=_('Options as published: a list of {"name", "value"}.'),
    )
    selection = models.JSONField(
        _("Selection"),
        default=dict,
        blank=True,
        help_text=_("How the unit is selected on its page, as the adapter knows."),
    )
    gtin = models.CharField(_("GTIN"), max_length=14, blank=True, db_index=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Listing Variant")
        verbose_name_plural = _("Listing Variants")
        ordering = ("listing", "external_id")
        constraints = (
            models.UniqueConstraint(
                fields=("listing", "external_id"),
                name="unique_variant_per_listing",
            ),
        )

    def __str__(self) -> str:
        """Return the listing and the options."""
        options = ", ".join(
            str(option.get("value"))
            for option in self.options or []
            if isinstance(option, dict)
        )
        return f"{self.listing} {options or self.external_id}"


class OfferSourceIdentity(BaseModel):
    """One name a source gives an offer, under a documented key scheme.

    ``scheme`` names how ``key`` was built (``legacy`` for the store slug and
    external id, ``vtex`` for item and seller, and so on). Keys never include a
    price, a stock level, a time or a featured position.
    """

    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="source_identities",
        verbose_name=_("Offer"),
    )
    namespace = models.SlugField(_("Namespace"), max_length=100)
    scheme = models.SlugField(_("Scheme"), max_length=50)
    scheme_version = models.PositiveSmallIntegerField(_("Scheme Version"), default=1)
    key = models.CharField(_("Key"), max_length=255)

    class Meta:
        """Meta options."""

        verbose_name = _("Offer Source Identity")
        verbose_name_plural = _("Offer Source Identities")
        constraints = (
            models.UniqueConstraint(
                fields=("namespace", "scheme", "scheme_version", "key"),
                name="unique_offer_source_identity",
            ),
        )

    def __str__(self) -> str:
        """Return the qualified key."""
        return f"{self.namespace}:{self.scheme}/{self.scheme_version}:{self.key}"


class FeaturedOfferObservation(BaseModel):
    """Which offer a listing variant featured at one moment.

    A buy box or default seller is a selection that changes. It is never the
    offer's identity, nor proof that every offer was enumerated.
    """

    listing_variant = models.ForeignKey(
        ListingVariant,
        on_delete=models.CASCADE,
        related_name="featured_observations",
        verbose_name=_("Listing Variant"),
    )
    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="featured_observations",
        verbose_name=_("Offer"),
    )
    batch = models.ForeignKey(
        "offers.ObservationBatch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="featured_offers",
        verbose_name=_("Batch"),
    )
    observed_at = models.DateTimeField(_("Observed At"), default=timezone.now)

    class Meta:
        """Meta options."""

        verbose_name = _("Featured Offer Observation")
        verbose_name_plural = _("Featured Offer Observations")
        ordering = ("-observed_at",)
        indexes = (models.Index(fields=["listing_variant", "-observed_at"]),)

    def __str__(self) -> str:
        """Return the variant and the featured offer."""
        moment = f"{self.observed_at:%d/%m %H:%M}"
        return f"{self.listing_variant} -> {self.offer_id} @ {moment}"
