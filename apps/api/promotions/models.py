"""Curated promotions: a stable identity and immutable, versioned terms.

A promotion's terms live in revisions. Everything a revision means -- its
conditions, scopes, codes, effects, reward terms and compatibility -- is owned
by that revision. Once published, none of it changes: an edit is a new
revision, and a suspended or archived one only changes status.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel


class PublishedRevisionError(ValidationError):
    """A published revision, or something it owns, cannot change."""


class Promotion(BaseModel):
    """A campaign's stable identity, issued by a seller, channel or programme."""

    title = models.CharField(_("Title"), max_length=200)
    issuer_seller = models.ForeignKey(
        "commerce.SellerAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotions",
        verbose_name=_("Issuing seller"),
    )
    issuer_channel = models.ForeignKey(
        "commerce.Channel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotions",
        verbose_name=_("Issuing channel"),
    )
    issuer_program = models.ForeignKey(
        "commerce.Program",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="promotions",
        verbose_name=_("Issuing programme"),
    )
    funder_raw = models.CharField(
        _("Funder"),
        max_length=200,
        blank=True,
        help_text=_("Who pays for it, when stated; never inferred."),
    )
    source_key = models.CharField(
        _("Source Key"),
        max_length=200,
        help_text=_("The campaign's identity at its issuer; a code alone is not."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Promotion")
        verbose_name_plural = _("Promotions")
        ordering = ("title",)
        constraints = (
            models.CheckConstraint(
                condition=Q(issuer_seller__isnull=False)
                | Q(issuer_channel__isnull=False)
                | Q(issuer_program__isnull=False),
                name="promotion_has_an_issuer",
            ),
            models.UniqueConstraint(
                fields=(
                    "issuer_seller",
                    "issuer_channel",
                    "issuer_program",
                    "source_key",
                ),
                name="unique_promotion_per_issuer_source",
            ),
        )

    def __str__(self) -> str:
        """Return the title."""
        return self.title


class PromotionRevision(BaseModel):
    """One version of a promotion's terms.

    ``draft`` is editable. ``informative`` records a real promotion whose terms
    are not enough to compute; ``executable`` enters calculations. Publishing
    (leaving draft) validates the terms and fixes ``content_hash``; after that
    only the status may move, to ``suspended`` or ``archived``.
    """

    class Status(models.TextChoices):
        """Lifecycle of a revision."""

        DRAFT = "draft", _("Draft")
        INFORMATIVE = "informative", _("Informative")
        EXECUTABLE = "executable", _("Executable")
        SUSPENDED = "suspended", _("Suspended")
        ARCHIVED = "archived", _("Archived")

    PUBLISHED = frozenset({"informative", "executable", "suspended", "archived"})

    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.PROTECT,
        related_name="revisions",
        verbose_name=_("Promotion"),
    )
    number = models.PositiveIntegerField(_("Number"))
    status = models.CharField(
        _("Status"),
        max_length=12,
        choices=Status,
        default=Status.DRAFT,
    )
    currency = models.ForeignKey(
        "commerce.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Currency"),
        help_text=_("The currency of every amount in these terms."),
    )
    starts_at = models.DateTimeField(_("Starts At"), null=True, blank=True)
    ends_at = models.DateTimeField(
        _("Ends At"),
        null=True,
        blank=True,
        help_text=_("Exclusive. Empty means unknown, not forever."),
    )
    timezone = models.CharField(
        _("Time Zone"),
        max_length=64,
        help_text=_("The zone the issuer dates the campaign in."),
    )
    verified_at = models.DateTimeField(_("Verified At"))
    review_by = models.DateTimeField(
        _("Review By"),
        null=True,
        blank=True,
        help_text=_("When the terms must be checked again."),
    )
    conditions = models.JSONField(
        _("Conditions"),
        default=dict,
        blank=True,
        help_text=_('A typed tree: {"root": null} or all/any/not over leaves.'),
    )
    ordering = models.JSONField(
        _("Effect Precedence"),
        default=list,
        blank=True,
        help_text=_('Edges [{"before": 1, "after": 2}] between effect positions.'),
    )
    limitations = models.TextField(
        _("Known Limitations"),
        blank=True,
        help_text=_("What the terms leave open: exclusions, stacking, dates."),
    )
    evidence = models.ManyToManyField(
        "offers.Evidence",
        related_name="promotion_revisions",
        verbose_name=_("Evidence"),
    )
    content_hash = models.CharField(_("Content Hash"), max_length=64, blank=True)
    published_at = models.DateTimeField(_("Published At"), null=True, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Promotion Revision")
        verbose_name_plural = _("Promotion Revisions")
        ordering = ("promotion", "-number")
        constraints = (
            models.UniqueConstraint(
                fields=("promotion", "number"),
                name="unique_revision_number",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True)
                | Q(starts_at__isnull=True)
                | Q(ends_at__gt=models.F("starts_at")),
                name="revision_ends_after_it_starts",
            ),
            models.CheckConstraint(
                condition=Q(status="draft") | Q(published_at__isnull=False),
                name="published_revision_has_a_date",
            ),
        )

    def __str__(self) -> str:
        """Return the promotion and revision number."""
        return f"{self.promotion} r{self.number} ({self.get_status_display()})"

    @property
    def is_published(self) -> bool:
        """Whether the revision left draft."""
        return self.published_at is not None

    FROZEN_EXEMPT = frozenset({"status", "updated_at"})

    def save(self, *args: object, **kwargs: object) -> None:
        """Refuse any change to published terms, and publishing outside the service.

        Only ``PromotionService`` publishes (it validates and hashes first).
        A published revision may only change status among published states.
        """
        # A form reads an empty JSON list or object back as None.
        self.conditions = self.conditions or {}
        self.ordering = self.ordering or []
        stored = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if stored is None or not stored.is_published:
            if self.status != self.Status.DRAFT:
                msg = _("Publish a revision through its promotion service.")
                raise PublishedRevisionError(msg)
            super().save(*args, **kwargs)
            return
        changed = [
            field.attname
            for field in self._meta.concrete_fields
            if field.attname not in self.FROZEN_EXEMPT
            and getattr(stored, field.attname) != getattr(self, field.attname)
        ]
        if changed or self.status not in self.PUBLISHED:
            msg = _("A published revision cannot change; create a new revision.")
            raise PublishedRevisionError(msg)
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Refuse to delete a published revision; archive it instead."""
        if self.is_published:
            msg = _("Archive a published revision instead of deleting it.")
            raise PublishedRevisionError(msg)
        return super().delete(*args, **kwargs)


class RevisionOwned(BaseModel):
    """A row a revision owns; frozen once the revision is published."""

    class Meta:
        """Meta options."""

        abstract = True

    def owning_revision(self) -> PromotionRevision:
        """Return the revision this row belongs to."""
        raise NotImplementedError

    def _refuse_if_published(self) -> None:
        if self.owning_revision().is_published:
            msg = _("A published revision cannot change; create a new revision.")
            raise PublishedRevisionError(msg)

    def save(self, *args: object, **kwargs: object) -> None:
        """Refuse writes under a published revision."""
        self._refuse_if_published()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Refuse deletes under a published revision."""
        self._refuse_if_published()
        return super().delete(*args, **kwargs)


class ActivationCode(RevisionOwned):
    """How a buyer activates the revision."""

    class Kind(models.TextChoices):
        """Activation mechanisms."""

        AUTOMATIC = "automatic", _("Automatic")
        PUBLIC_CODE = "public_code", _("Public code")
        PERSONAL_CODE = "personal_code", _("Personal code")
        BALANCE_REDEMPTION = "balance_redemption", _("Balance redemption")
        REQUIRED_ACTION = "required_action", _("Required action")

    revision = models.ForeignKey(
        PromotionRevision,
        on_delete=models.CASCADE,
        related_name="codes",
        verbose_name=_("Revision"),
    )
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    code = models.CharField(_("Code"), max_length=100, blank=True)
    channel_scope = models.CharField(
        _("Channel Scope"),
        max_length=10,
        choices=[("any", _("Any")), ("web", _("Web")), ("app", _("App"))],
        default="any",
    )
    instructions = models.CharField(_("Instructions"), max_length=255, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Activation Code")
        verbose_name_plural = _("Activation Codes")
        constraints = (
            models.CheckConstraint(
                condition=~Q(kind__in=("public_code", "personal_code")) | ~Q(code=""),
                name="code_kind_has_a_code",
            ),
        )

    def __str__(self) -> str:
        """Return the kind, hiding personal codes."""
        if self.kind == self.Kind.PERSONAL_CODE:
            return str(self.get_kind_display())
        return f"{self.get_kind_display()} {self.code}".strip()

    def owning_revision(self) -> PromotionRevision:
        """Return the revision."""
        return self.revision


class PromotionScope(RevisionOwned):
    """What qualifies for the revision, or what it targets, included or excluded."""

    class Role(models.TextChoices):
        """Qualification or target."""

        QUALIFICATION = "qualification", _("Qualifies")
        TARGET = "target", _("Receives the benefit")

    class Mode(models.TextChoices):
        """Include or exclude; exclusions win."""

        INCLUDE = "include", _("Include")
        EXCLUDE = "exclude", _("Exclude")

    class Kind(models.TextChoices):
        """What a scope row names."""

        CHANNEL = "channel", _("Channel")
        MARKET = "market", _("Market")
        SELLER_ACCOUNT = "seller_account", _("Seller account")
        MERCHANT = "merchant", _("Merchant")
        BRAND = "brand", _("Brand")
        CATEGORY = "category", _("Category")
        PRODUCT = "product", _("Product")
        LISTING = "listing", _("Listing")
        LISTING_VARIANT = "listing_variant", _("Listing variant")
        OFFER = "offer", _("Offer")
        EXTERNAL_CATEGORY = "external_category", _("Store category")

    revision = models.ForeignKey(
        PromotionRevision,
        on_delete=models.CASCADE,
        related_name="scopes",
        verbose_name=_("Revision"),
    )
    role = models.CharField(_("Role"), max_length=15, choices=Role)
    mode = models.CharField(
        _("Mode"),
        max_length=7,
        choices=Mode,
        default=Mode.INCLUDE,
    )
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    ref_id = models.PositiveBigIntegerField(
        _("Reference ID"),
        null=True,
        blank=True,
        help_text=_("The id of the named row."),
    )
    external_ref = models.CharField(
        _("External Reference"),
        max_length=200,
        blank=True,
        help_text=_("A store category name or id, verbatim."),
    )
    combine = models.CharField(
        _("Combine"),
        max_length=12,
        choices=[("union", _("Union")), ("intersection", _("Intersection"))],
        default="union",
        help_text=_("How included rows of different kinds combine."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Promotion Scope")
        verbose_name_plural = _("Promotion Scopes")
        constraints = (
            models.CheckConstraint(
                condition=(Q(kind="external_category") & ~Q(external_ref=""))
                | (~Q(kind="external_category") & Q(ref_id__isnull=False)),
                name="scope_names_its_row",
            ),
        )

    def __str__(self) -> str:
        """Return role, mode and what is named."""
        named = self.external_ref or f"{self.kind} #{self.ref_id}"
        return f"{self.role} {self.mode} {named}"

    def owning_revision(self) -> PromotionRevision:
        """Return the revision."""
        return self.revision


class PromotionEffect(RevisionOwned):
    """What the revision grants, on what basis, to which target."""

    class Kind(models.TextChoices):
        """Effect kinds; ``parameters`` is typed per kind."""

        PERCENTAGE = "percentage", _("Percentage off")
        FIXED_AMOUNT = "fixed_amount", _("Amount off")
        FIXED_PRICE = "fixed_price", _("Fixed price")
        SHIPPING_DISCOUNT = "shipping_discount", _("Shipping discount")
        CASHBACK = "cashback", _("Cashback")
        POINTS = "points", _("Points")
        GIFT = "gift", _("Gift")
        MULTIBUY = "multibuy", _("Buy X pay Y")
        TIERED = "tiered", _("Quantity tiers")
        SUBSCRIPTION = "subscription", _("Subscription price")

    class Stage(models.TextChoices):
        """When in the calculation the effect applies."""

        CATALOG = "catalog", _("Catalog")
        ORDER = "order", _("Order")
        PAYMENT = "payment", _("Payment")
        SHIPPING = "shipping", _("Shipping")
        REWARD = "reward", _("Reward")

    class Basis(models.TextChoices):
        """The value the effect is computed on."""

        INITIAL = "initial", _("Initial price")
        CURRENT = "current", _("Price after earlier effects")
        ELIGIBLE_SUBTOTAL = "eligible_subtotal", _("Eligible subtotal")
        ORDER_TOTAL = "order_total", _("Order total")
        COMPONENT = "component", _("A component (shipping)")

    class Target(models.TextChoices):
        """What receives the effect."""

        ITEM = "item", _("Each item")
        LINE = "line", _("Each line")
        GROUP = "group", _("A checkout group")
        ORDER = "order", _("The order")
        SHIPPING = "shipping", _("Shipping")

    class Allocation(models.TextChoices):
        """How the effect is spread."""

        PER_UNIT = "per_unit", _("Per unit")
        PER_LINE = "per_line", _("Per line")
        ONCE = "once", _("Once")
        PRORATED = "prorated", _("Prorated over eligible lines")

    revision = models.ForeignKey(
        PromotionRevision,
        on_delete=models.CASCADE,
        related_name="effects",
        verbose_name=_("Revision"),
    )
    position = models.PositiveSmallIntegerField(
        _("Position"),
        help_text=_("Names the effect in the precedence edges."),
    )
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    stage = models.CharField(_("Stage"), max_length=10, choices=Stage)
    basis = models.CharField(_("Basis"), max_length=20, choices=Basis)
    target = models.CharField(_("Target"), max_length=10, choices=Target)
    allocation = models.CharField(_("Allocation"), max_length=10, choices=Allocation)
    parameters = models.JSONField(_("Parameters"), default=dict, blank=True)
    cap = models.DecimalField(
        _("Cap"),
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=_("The most the effect gives, in the revision's currency."),
    )
    max_applications = models.PositiveIntegerField(
        _("Max Applications"),
        null=True,
        blank=True,
    )
    consumes_units = models.BooleanField(
        _("Consumes units"),
        default=True,
        help_text=_("Units it uses cannot qualify another effect."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Promotion Effect")
        verbose_name_plural = _("Promotion Effects")
        ordering = ("revision", "position")
        constraints = (
            models.UniqueConstraint(
                fields=("revision", "position"),
                name="unique_effect_position",
            ),
            models.CheckConstraint(
                condition=Q(cap__isnull=True) | Q(cap__gte=0),
                name="effect_cap_not_negative",
            ),
        )

    def __str__(self) -> str:
        """Return position and kind."""
        return f"#{self.position} {self.get_kind_display()}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Store parameterless effects as an empty object, not null."""
        self.parameters = self.parameters or {}
        super().save(*args, **kwargs)

    def owning_revision(self) -> PromotionRevision:
        """Return the revision."""
        return self.revision


class RewardTerms(RevisionOwned):
    """How a deferred reward is credited: money, restricted credit or points."""

    class CreditedAs(models.TextChoices):
        """What the buyer receives."""

        MONEY = "money", _("Money")
        RESTRICTED_CREDIT = "restricted_credit", _("Restricted credit")
        POINTS = "points", _("Points")

    effect = models.OneToOneField(
        PromotionEffect,
        on_delete=models.CASCADE,
        related_name="reward_terms",
        verbose_name=_("Effect"),
    )
    program = models.ForeignKey(
        "commerce.Program",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reward_terms",
        verbose_name=_("Programme"),
    )
    credited_as = models.CharField(_("Credited As"), max_length=20, choices=CreditedAs)
    eligible_basis = models.CharField(
        _("Eligible Basis"),
        max_length=30,
        choices=[
            ("items_after_discounts", _("Items after discounts")),
            ("items_before_discounts", _("Items before discounts")),
            ("order_total", _("Order total")),
        ],
        default="items_after_discounts",
        help_text=_("Shipping is never in the basis unless the terms say so."),
    )
    includes_shipping = models.BooleanField(_("Includes shipping"), default=False)
    rate = models.DecimalField(
        _("Rate"),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    cap = models.DecimalField(
        _("Cap"),
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
    )
    cap_period = models.CharField(
        _("Cap Period"),
        max_length=12,
        choices=[
            ("transaction", _("Per transaction")),
            ("month", _("Per month")),
            ("campaign", _("Per campaign")),
        ],
        blank=True,
    )
    minimum = models.DecimalField(
        _("Minimum Purchase"),
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
    )
    tracking_required = models.BooleanField(_("Tracking required"), default=False)
    credit_delay_days = models.PositiveIntegerField(
        _("Credit Delay (days)"),
        null=True,
        blank=True,
    )
    delay_from = models.CharField(
        _("Delay Counted From"),
        max_length=12,
        choices=[
            ("purchase", _("Purchase")),
            ("delivery", _("Delivery")),
            ("confirmation", _("Confirmation")),
            ("statement", _("Card statement")),
        ],
        blank=True,
    )
    expires_after_days = models.PositiveIntegerField(
        _("Expires After (days)"),
        null=True,
        blank=True,
    )
    redemption_minimum = models.DecimalField(
        _("Redemption Minimum"),
        max_digits=19,
        decimal_places=6,
        null=True,
        blank=True,
    )
    cancellation_terms = models.TextField(_("Cancellation Terms"), blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Reward Terms")
        verbose_name_plural = _("Reward Terms")
        constraints = (
            models.CheckConstraint(
                condition=Q(rate__isnull=True) | (Q(rate__gt=0) & Q(rate__lte=100)),
                name="reward_rate_is_a_percentage",
            ),
        )

    def __str__(self) -> str:
        """Return the effect and what it credits."""
        return f"{self.effect} as {self.get_credited_as_display()}"

    def owning_revision(self) -> PromotionRevision:
        """Return the effect's revision."""
        return self.effect.revision


class CompatibilityRule(RevisionOwned):
    """Whether this revision combines with another promotion, kind or programme."""

    class OtherKind(models.TextChoices):
        """What the rule is about."""

        PROMOTION = "promotion", _("A promotion")
        EFFECT_KIND = "effect_kind", _("Any effect of a kind")
        PROGRAM = "program", _("A programme")
        PAYMENT_METHOD = "payment_method", _("A payment method's own discount")

    class Verdict(models.TextChoices):
        """Allowed, forbidden or unknown."""

        ALLOWED = "allowed", _("Allowed")
        FORBIDDEN = "forbidden", _("Forbidden")
        UNKNOWN = "unknown", _("Unknown")

    class Chooser(models.TextChoices):
        """Who picks between incompatible benefits."""

        STORE_IMPOSED = "store_imposed", _("The store")
        BUYER_CHOICE = "buyer_choice", _("The buyer")

    revision = models.ForeignKey(
        PromotionRevision,
        on_delete=models.CASCADE,
        related_name="compatibility",
        verbose_name=_("Revision"),
    )
    other_kind = models.CharField(_("About"), max_length=15, choices=OtherKind)
    other_ref = models.CharField(
        _("Which"),
        max_length=100,
        help_text=_("A promotion id, an effect kind, a programme id or a method code."),
    )
    verdict = models.CharField(_("Verdict"), max_length=10, choices=Verdict)
    chooser = models.CharField(
        _("Chooser"),
        max_length=15,
        choices=Chooser,
        default=Chooser.BUYER_CHOICE,
    )
    evidence = models.ForeignKey(
        "offers.Evidence",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="compatibility_rules",
        verbose_name=_("Evidence"),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Compatibility Rule")
        verbose_name_plural = _("Compatibility Rules")
        constraints = (
            models.UniqueConstraint(
                fields=("revision", "other_kind", "other_ref"),
                name="one_rule_per_other",
            ),
        )

    def __str__(self) -> str:
        """Return the rule."""
        return f"{self.verdict} with {self.other_kind} {self.other_ref}"

    def owning_revision(self) -> PromotionRevision:
        """Return the revision."""
        return self.revision


class PurchaseRoute(BaseModel):
    """How to buy an offer so that the priced scenario holds.

    A route that does not fix the seller or the variant says so; the scenario
    then reports the limitation instead of promising the exact offer.
    """

    class Kind(models.TextChoices):
        """Route kinds."""

        DIRECT = "direct", _("Direct")
        AFFILIATE = "affiliate", _("Affiliate link")
        CASHBACK_ACTIVATION = "cashback_activation", _("Cashback activation")
        MARKETPLACE_LISTING = "marketplace_listing", _("Marketplace listing")

    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="purchase_routes",
        verbose_name=_("Offer"),
    )
    listing = models.ForeignKey(
        "offers.Listing",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="purchase_routes",
        verbose_name=_("Listing"),
    )
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    program = models.ForeignKey(
        "commerce.Program",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_routes",
        verbose_name=_("Programme"),
    )
    url = models.URLField(_("URL"), max_length=1000)
    fixes_variant = models.BooleanField(_("Opens the exact variant"), default=False)
    fixes_seller = models.BooleanField(_("Opens the exact seller"), default=False)
    compatible_programs = models.ManyToManyField(
        "commerce.Program",
        blank=True,
        related_name="compatible_routes",
        verbose_name=_("Compatible programmes"),
        help_text=_("Programmes whose tracking survives this route; none by default."),
    )
    instructions = models.TextField(_("Instructions"), blank=True)
    evidence = models.ForeignKey(
        "offers.Evidence",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_routes",
        verbose_name=_("Evidence"),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Purchase Route")
        verbose_name_plural = _("Purchase Routes")
        constraints = (
            models.CheckConstraint(
                condition=Q(offer__isnull=False) | Q(listing__isnull=False),
                name="route_names_offer_or_listing",
            ),
        )

    def __str__(self) -> str:
        """Return the kind and URL."""
        return f"{self.get_kind_display()}: {self.url}"
