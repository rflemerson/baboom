"""What a source said, when, in which context, and how much of it was read.

Observations are append-only facts. A batch groups the values read together,
coverage says which dimensions of a partition were read completely, and each
price observation says what role the value plays, where in the purchase it was
captured, how it may be paid and what it already includes.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel

from .offer import StockStatus

MONEY_DIGITS = 19
MONEY_PLACES = 6


def money_field(label: str, **kwargs: object) -> models.DecimalField:
    """Return a monetary field that keeps the source's precision."""
    return models.DecimalField(
        _(label),
        max_digits=MONEY_DIGITS,
        decimal_places=MONEY_PLACES,
        **kwargs,
    )


class ObservationBatch(BaseModel):
    """Values one adapter read together, from one market, in one request set."""

    class Status(models.TextChoices):
        """How the read ended."""

        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        PARTIAL = "partial", _("Partial")
        FAILED = "failed", _("Failed")

    market = models.ForeignKey(
        "commerce.Market",
        on_delete=models.PROTECT,
        related_name="observation_batches",
        verbose_name=_("Market"),
    )
    adapter = models.CharField(_("Adapter"), max_length=50)
    adapter_version = models.CharField(_("Adapter Version"), max_length=20)
    started_at = models.DateTimeField(_("Started At"), default=timezone.now)
    finished_at = models.DateTimeField(_("Finished At"), null=True, blank=True)
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=Status,
        default=Status.RUNNING,
    )
    request_context = models.JSONField(
        _("Request Context"),
        default=dict,
        blank=True,
        help_text=_(
            "Endpoint, region, sales channel and a hash of any postal code; "
            "never a personal value in clear.",
        ),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Observation Batch")
        verbose_name_plural = _("Observation Batches")
        ordering = ("-started_at",)

    def __str__(self) -> str:
        """Return adapter, market and start."""
        return f"{self.adapter} {self.market.namespace} @ {self.started_at:%d/%m %H:%M}"


class CollectionCoverage(BaseModel):
    """How completely one dimension of one partition was read in a batch.

    Absence is evidence only inside a complete partition of the same
    dimension: a full variant list with partial sellers delists no seller.
    """

    class Dimension(models.TextChoices):
        """What was enumerated."""

        VARIANTS = "variants", _("Variants")
        SELLERS = "sellers", _("Sellers")
        OFFERS = "offers", _("Offers")
        PAYMENT_PRICES = "payment_prices", _("Payment prices")
        AVAILABILITY = "availability", _("Availability")
        PAGINATION = "pagination", _("Pagination")

    class Status(models.TextChoices):
        """How much of the dimension was read."""

        COMPLETE = "complete", _("Complete")
        PARTIAL = "partial", _("Partial")
        FAILED = "failed", _("Failed")
        ACCESS_UNAVAILABLE = "access_unavailable", _("Access unavailable")

    batch = models.ForeignKey(
        ObservationBatch,
        on_delete=models.CASCADE,
        related_name="coverage",
        verbose_name=_("Batch"),
    )
    dimension = models.CharField(_("Dimension"), max_length=20, choices=Dimension)
    partition = models.CharField(
        _("Partition"),
        max_length=255,
        help_text=_("What was enumerated: a listing id, a category, a page range."),
    )
    status = models.CharField(_("Status"), max_length=20, choices=Status)
    reason = models.CharField(_("Reason"), max_length=255, blank=True)
    cursor = models.CharField(
        _("Cursor"),
        max_length=255,
        blank=True,
        help_text=_("Where enumeration stopped, when the source pages it."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Collection Coverage")
        verbose_name_plural = _("Collection Coverage")
        constraints = (
            models.UniqueConstraint(
                fields=("batch", "dimension", "partition"),
                name="unique_coverage_per_batch_dimension_partition",
            ),
        )

    def __str__(self) -> str:
        """Return dimension, partition and status."""
        return f"{self.dimension} {self.partition}: {self.status}"


class Evidence(BaseModel):
    """What a fact rests on, without storing the page it came from."""

    class Kind(models.TextChoices):
        """What kind of source proves the fact."""

        CATALOG_RESPONSE = "catalog_response", _("Catalog response")
        CART_QUOTE = "cart_quote", _("Cart quote")
        PRODUCT_PAGE = "product_page", _("Product page")
        REGULATION = "regulation", _("Regulation")
        ANNOUNCEMENT = "announcement", _("Announcement")
        THEME_SETTING = "theme_setting", _("Theme setting")
        MANUAL = "manual", _("Manual reading")

    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    source_url = models.URLField(_("Source URL"), max_length=500, blank=True)
    observed_at = models.DateTimeField(_("Observed At"), default=timezone.now)
    excerpt = models.TextField(
        _("Excerpt"),
        blank=True,
        help_text=_("The words that prove it, verbatim; never a whole page."),
    )
    content_hash = models.CharField(_("Content Hash"), max_length=64, blank=True)
    captured_by = models.CharField(
        _("Captured By"),
        max_length=100,
        blank=True,
        help_text=_("The adapter, or the curator who read it."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Evidence")
        verbose_name_plural = _("Evidence")
        ordering = ("-observed_at",)

    def __str__(self) -> str:
        """Return kind and source."""
        return f"{self.get_kind_display()}: {self.source_url or self.excerpt[:60]}"


class PriceRole(models.TextChoices):
    """Whether a value is payable or only a reference."""

    PAYABLE = "payable", _("Payable")
    REFERENCE = "reference", _("Reference")


class CaptureStage(models.TextChoices):
    """Where in the purchase the value was read."""

    CATALOG = "catalog", _("Catalog")
    PRODUCT_PAGE = "product_page", _("Product page")
    CART = "cart", _("Cart")
    CHECKOUT = "checkout", _("Checkout")


class EvidenceLevel(models.TextChoices):
    """What the value proves."""

    ADVERTISED = "advertised", _("Advertised")
    OBSERVED_IN_CATALOG = "observed_in_catalog", _("Observed in catalog")
    QUOTED_FOR_CONTEXT = "quoted_for_context", _("Quoted for a context")


class PaymentScope(models.TextChoices):
    """Which payments a value holds for.

    ``unknown`` is not ``any``: a store's price whose payment the source does
    not state may still differ by method. ``cash`` is a single, immediate
    payment whose method the source does not name.
    """

    UNKNOWN = "unknown", _("Unknown")
    ANY = "any", _("Any method")
    CASH = "cash", _("Paid at once, method not named")
    METHOD = "method", _("A named method")


class Tristate(models.TextChoices):
    """A yes, a no, or an unknown."""

    YES = "yes", _("Yes")
    NO = "no", _("No")
    UNKNOWN = "unknown", _("Unknown")


class OfferPriceObservation(BaseModel):
    """One value a source stated for an offer, or for a variant without a seller.

    Selecting the Pix observation is choosing a base, never a discount to apply
    again: whatever a value already includes is listed in
    ``included_adjustments``. A value computed from an announced rate is
    ``derived`` and points at what it was derived from.
    """

    class Semantics(models.TextChoices):
        """Whether the meaning of the value is known."""

        KNOWN = "known", _("Known")
        LEGACY_UNKNOWN = "legacy_unknown", _("Legacy, meaning unknown")

    class Composition(models.TextChoices):
        """How much of what the value includes is known."""

        KNOWN = "known", _("Known")
        PARTIAL = "partial", _("Partial")
        UNKNOWN = "unknown", _("Unknown")

    class AmountBasis(models.TextChoices):
        """What quantity the amount prices."""

        UNIT = "unit", _("One unit")
        LINE = "line", _("A line")
        ORDER = "order", _("An order")

    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="price_points",
        verbose_name=_("Offer"),
    )
    listing_variant = models.ForeignKey(
        "offers.ListingVariant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="aggregate_price_points",
        verbose_name=_("Listing Variant"),
        help_text=_("A price the source states without naming a seller."),
    )
    batch = models.ForeignKey(
        ObservationBatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="price_points",
        verbose_name=_("Batch"),
    )
    amount = money_field("Amount")
    currency = models.ForeignKey(
        "commerce.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Currency"),
    )
    amount_basis = models.CharField(
        _("Amount Basis"),
        max_length=5,
        choices=AmountBasis,
        default=AmountBasis.UNIT,
    )
    role = models.CharField(_("Role"), max_length=10, choices=PriceRole)
    capture_stage = models.CharField(
        _("Capture Stage"),
        max_length=15,
        choices=CaptureStage,
        default=CaptureStage.CATALOG,
    )
    evidence_level = models.CharField(
        _("Evidence Level"),
        max_length=20,
        choices=EvidenceLevel,
        default=EvidenceLevel.OBSERVED_IN_CATALOG,
    )
    semantics = models.CharField(
        _("Semantics"),
        max_length=15,
        choices=Semantics,
        default=Semantics.KNOWN,
    )
    payment_scope = models.CharField(
        _("Payment Scope"),
        max_length=10,
        choices=PaymentScope,
        default=PaymentScope.UNKNOWN,
    )
    payment_method = models.ForeignKey(
        "commerce.PaymentMethod",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Payment Method"),
    )
    payment_provider_raw = models.CharField(
        _("Payment provider as published"),
        max_length=100,
        blank=True,
    )
    payment_label_raw = models.CharField(
        _("Payment label as published"),
        max_length=100,
        blank=True,
    )
    installment_count = models.PositiveSmallIntegerField(
        _("Installments"),
        null=True,
        blank=True,
    )
    installment_amount = money_field("Installment Amount", null=True, blank=True)
    interest = models.CharField(
        _("Interest"),
        max_length=7,
        choices=Tristate,
        default=Tristate.UNKNOWN,
        help_text=_("Whether the installments carry interest."),
    )
    quantity_min = models.PositiveIntegerField(_("Minimum Quantity"), default=1)
    quantity_max = models.PositiveIntegerField(
        _("Maximum Quantity"),
        null=True,
        blank=True,
    )
    condition_key = models.CharField(
        _("Condition Key"),
        max_length=64,
        db_index=True,
        help_text=_("Hash of the normalized context; never amount or time."),
    )
    context = models.JSONField(
        _("Context"),
        default=dict,
        blank=True,
        help_text=_("Membership, destination and other conditions, typed."),
    )
    tax_inclusion = models.CharField(
        _("Tax Included"),
        max_length=7,
        choices=Tristate,
        default=Tristate.UNKNOWN,
    )
    source_field = models.CharField(_("Source Field"), max_length=100)
    evidence = models.ForeignKey(
        Evidence,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="price_points",
        verbose_name=_("Evidence"),
    )
    observed_at = models.DateTimeField(_("Observed At"), default=timezone.now)
    recorded_at = models.DateTimeField(_("Recorded At"), default=timezone.now)
    confirmed_at = models.DateTimeField(
        _("Confirmed At"),
        default=timezone.now,
        help_text=_("The last read that stated this value."),
    )
    withdrawn_at = models.DateTimeField(
        _("Withdrawn At"),
        null=True,
        blank=True,
        help_text=_("The first complete read that no longer stated this condition."),
    )
    valid_until = models.DateTimeField(_("Valid Until"), null=True, blank=True)
    fresh_until = models.DateTimeField(_("Fresh Until"), null=True, blank=True)
    composition = models.CharField(
        _("Composition"),
        max_length=7,
        choices=Composition,
        default=Composition.UNKNOWN,
    )
    included_adjustments = models.JSONField(
        _("Included Adjustments"),
        default=list,
        blank=True,
        help_text=_('What the value already includes: [{"kind", "amount", ...}].'),
    )
    derived_from = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="derivations",
        verbose_name=_("Derived From"),
    )
    derivation = models.CharField(
        _("Derivation"),
        max_length=30,
        blank=True,
        help_text=_("How a derived value was computed, e.g. advertised_rate."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Offer Price Observation")
        verbose_name_plural = _("Offer Price Observations")
        ordering = ("-observed_at",)
        indexes = (
            models.Index(fields=["offer", "condition_key", "-observed_at"]),
            models.Index(fields=["listing_variant", "condition_key", "-observed_at"]),
        )
        constraints = (
            models.CheckConstraint(
                condition=Q(offer__isnull=False, listing_variant__isnull=True)
                | Q(offer__isnull=True, listing_variant__isnull=False),
                name="price_point_has_one_subject",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="price_point_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(payment_method__isnull=True) | Q(payment_scope="method"),
                name="price_point_method_only_with_method_scope",
            ),
            models.CheckConstraint(
                condition=Q(derived_from__isnull=True) | ~Q(derivation=""),
                name="price_point_derivation_named",
            ),
        )

    def __str__(self) -> str:
        """Return the subject, role and amount."""
        subject = self.offer_id or f"variant {self.listing_variant_id}"
        return f"{subject} {self.role} {self.currency_id} {self.amount}"


class AvailabilityObservation(BaseModel):
    """What a source said about stock at one moment.

    Stock is not deliverability: ``destination`` is empty unless the reading
    was for a delivery destination.
    """

    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="availability_points",
        verbose_name=_("Offer"),
    )
    batch = models.ForeignKey(
        ObservationBatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="availability_points",
        verbose_name=_("Batch"),
    )
    status = models.CharField(_("Status"), max_length=1, choices=StockStatus)
    quantity = models.IntegerField(_("Quantity"), null=True, blank=True)
    destination = models.JSONField(_("Destination"), default=dict, blank=True)
    source_field = models.CharField(_("Source Field"), max_length=100, blank=True)
    observed_at = models.DateTimeField(_("Observed At"), default=timezone.now)

    class Meta:
        """Meta options."""

        verbose_name = _("Availability Observation")
        verbose_name_plural = _("Availability Observations")
        ordering = ("-observed_at",)
        indexes = (models.Index(fields=["offer", "-observed_at"]),)

    def __str__(self) -> str:
        """Return the offer and status."""
        return f"{self.offer_id} {self.get_status_display()}"
