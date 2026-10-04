"""Who sells, where, in which currency, and how a buyer can pay.

This app imports only ``common``. Offers, promotions and pricing build on it;
it knows none of them, nor the catalog.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel

ISO_CURRENCY = RegexValidator(r"^[A-Z]{3}$", _("Use an ISO 4217 code."))
ISO_COUNTRY = RegexValidator(r"^[A-Z]{2}$", _("Use an ISO 3166-1 alpha-2 code."))
MAX_MINOR_UNIT = 4


class Currency(models.Model):
    """An ISO 4217 currency and the precision it is charged in."""

    code = models.CharField(
        _("Code"),
        max_length=3,
        primary_key=True,
        validators=[ISO_CURRENCY],
    )
    minor_unit = models.PositiveSmallIntegerField(
        _("Minor Unit"),
        validators=[MaxValueValidator(MAX_MINOR_UNIT)],
        help_text=_("Decimal places a price is charged in: 2 for BRL, 0 for JPY."),
    )
    name = models.CharField(_("Name"), max_length=60, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")
        ordering = ("code",)

    def __str__(self) -> str:
        """Return the ISO code."""
        return self.code


class Channel(BaseModel):
    """Where a buyer checks out: an independent store, a marketplace or an app."""

    class Kind(models.TextChoices):
        """How the channel sells."""

        INDEPENDENT_STORE = "independent_store", _("Independent store")
        MARKETPLACE = "marketplace", _("Marketplace")
        APP = "app", _("App")

    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    name = models.CharField(_("Name"), max_length=100, unique=True)
    adapter = models.CharField(
        _("Adapter"),
        max_length=50,
        blank=True,
        help_text=_("The integration that reads it, e.g. vtex or shopify."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Channel")
        verbose_name_plural = _("Channels")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return the channel name."""
        return self.name


class Market(BaseModel):
    """One commercial partition of a channel: a country, a currency, a clock.

    ``namespace`` scopes every external id read from it, so the same id in two
    markets never names the same thing.
    """

    channel = models.ForeignKey(
        Channel,
        on_delete=models.PROTECT,
        related_name="markets",
        verbose_name=_("Channel"),
    )
    country = models.CharField(_("Country"), max_length=2, validators=[ISO_COUNTRY])
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="markets",
        verbose_name=_("Currency"),
    )
    timezone = models.CharField(
        _("Time Zone"),
        max_length=64,
        help_text=_("IANA zone campaigns of this market are dated in."),
    )
    namespace = models.SlugField(
        _("Namespace"),
        max_length=100,
        unique=True,
        help_text=_("Scopes external ids; the scraper's store slug for a store."),
    )
    provenance = models.CharField(
        _("Provenance"),
        max_length=20,
        choices=[
            ("observed", _("Observed in the source")),
            ("source_contract", _("Declared by the source contract")),
            ("curated", _("Curated")),
        ],
        default="curated",
        help_text=_("How country and currency are known."),
    )
    tax_inclusion = models.CharField(
        _("Taxes in prices"),
        max_length=8,
        choices=[
            ("included", _("Prices include every tax")),
            ("excluded", _("Taxes are charged on top")),
            ("unknown", _("Unknown")),
        ],
        default="unknown",
        help_text=_("Whether a shelf price already carries the market's taxes."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Market")
        verbose_name_plural = _("Markets")
        ordering = ("namespace",)
        constraints = (
            models.UniqueConstraint(
                fields=("channel", "country"),
                name="one_market_per_channel_country",
            ),
        )

    def __str__(self) -> str:
        """Return channel and country."""
        return f"{self.channel.name} ({self.country})"


class SellerAccount(BaseModel):
    """A seller inside one market, known by the id that market gives it.

    A seller is never matched by name. A price whose seller the source does not
    state belongs to no account; an account whose identity is known only in
    part is ``unresolved`` and waits for review.
    """

    class Resolution(models.TextChoices):
        """Whether the account is a known seller."""

        RESOLVED = "resolved", _("Resolved")
        UNRESOLVED = "unresolved", _("Unresolved")

    market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        related_name="seller_accounts",
        verbose_name=_("Market"),
    )
    external_id = models.CharField(
        _("External ID"),
        max_length=100,
        blank=True,
        help_text=_("The seller id the market publishes; empty when it has none."),
    )
    name_raw = models.CharField(_("Name as published"), max_length=200, blank=True)
    is_channel_owner = models.BooleanField(
        _("Channel owner"),
        default=False,
        help_text=_("The account of the store that runs the channel."),
    )
    resolution = models.CharField(
        _("Resolution"),
        max_length=10,
        choices=Resolution,
        default=Resolution.RESOLVED,
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Seller Account")
        verbose_name_plural = _("Seller Accounts")
        ordering = ("market", "name_raw")
        constraints = (
            models.UniqueConstraint(
                fields=("market", "external_id"),
                condition=~Q(external_id=""),
                name="unique_seller_external_id_per_market",
            ),
            models.UniqueConstraint(
                fields=("market",),
                condition=Q(is_channel_owner=True),
                name="one_channel_owner_per_market",
            ),
        )

    def __str__(self) -> str:
        """Return the seller and its market."""
        label = self.name_raw or self.external_id or _("owner")
        return f"{label} @ {self.market.namespace}"


class Merchant(BaseModel):
    """A company, grouping seller accounts a curator verified as its own."""

    name = models.CharField(_("Name"), max_length=200, unique=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Merchant")
        verbose_name_plural = _("Merchants")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return the name."""
        return self.name


class MerchantBinding(BaseModel):
    """A curated, evidenced claim that an account belongs to a merchant."""

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="bindings",
        verbose_name=_("Merchant"),
    )
    seller_account = models.OneToOneField(
        SellerAccount,
        on_delete=models.CASCADE,
        related_name="merchant_binding",
        verbose_name=_("Seller Account"),
    )
    evidence = models.TextField(
        _("Evidence"),
        help_text=_("What shows the account belongs to the merchant."),
    )
    verified_at = models.DateTimeField(_("Verified At"))

    class Meta:
        """Meta options."""

        verbose_name = _("Merchant Binding")
        verbose_name_plural = _("Merchant Bindings")

    def __str__(self) -> str:
        """Return the binding."""
        return f"{self.seller_account} -> {self.merchant}"


class FulfillmentProfile(BaseModel):
    """Who ships an offer, as the market states it."""

    class Kind(models.TextChoices):
        """Who executes delivery."""

        SELLER = "seller", _("The seller")
        CHANNEL = "channel", _("The channel")
        THIRD_PARTY = "third_party", _("A third party")
        UNKNOWN = "unknown", _("Unknown")

    market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        related_name="fulfillment_profiles",
        verbose_name=_("Market"),
    )
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    label_raw = models.CharField(_("Label as published"), max_length=100, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Fulfillment Profile")
        verbose_name_plural = _("Fulfillment Profiles")
        constraints = (
            models.UniqueConstraint(
                fields=("market", "kind", "label_raw"),
                name="unique_fulfillment_profile",
            ),
        )

    def __str__(self) -> str:
        """Return the kind and label."""
        return f"{self.get_kind_display()} {self.label_raw}".strip()


class PaymentMethod(BaseModel):
    """A way to pay, in a family the engine understands.

    Pix is ``instant_transfer`` with code ``pix`` in the Brazilian market: a
    method, never a phase of the calculation.
    """

    class Family(models.TextChoices):
        """Payment families."""

        CARD = "card", _("Card")
        INSTANT_TRANSFER = "instant_transfer", _("Instant transfer")
        BANK_SLIP = "bank_slip", _("Bank slip")
        WALLET = "wallet", _("Wallet")
        DEFERRED = "deferred", _("Deferred payment")
        STORE_CREDIT = "store_credit", _("Store credit")
        OTHER = "other", _("Other")

    family = models.CharField(_("Family"), max_length=20, choices=Family)
    code = models.SlugField(_("Code"), max_length=50)
    name = models.CharField(_("Name"), max_length=100)
    country = models.CharField(
        _("Country"),
        max_length=2,
        blank=True,
        validators=[ISO_COUNTRY],
        help_text=_("Empty for a method used in every market."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
        ordering = ("code",)
        constraints = (
            models.UniqueConstraint(
                fields=("code", "country"),
                name="unique_payment_method_per_country",
            ),
        )

    def __str__(self) -> str:
        """Return the name."""
        return self.name


class PaymentProvider(BaseModel):
    """An acquirer, wallet, issuer or gateway named by a source."""

    class Kind(models.TextChoices):
        """Provider roles."""

        ACQUIRER = "acquirer", _("Acquirer")
        WALLET = "wallet", _("Wallet")
        ISSUER = "issuer", _("Issuer")
        GATEWAY = "gateway", _("Gateway")
        CARD_NETWORK = "card_network", _("Card network")

    name = models.CharField(_("Name"), max_length=100, unique=True)
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)

    class Meta:
        """Meta options."""

        verbose_name = _("Payment Provider")
        verbose_name_plural = _("Payment Providers")
        ordering = ("name",)

    def __str__(self) -> str:
        """Return the name."""
        return self.name


class Program(BaseModel):
    """A cashback, loyalty, membership, subscription or card programme.

    Its issuer scopes every claim about it: being new to the channel, to the
    seller or to the programme are three different facts.
    """

    class Kind(models.TextChoices):
        """Programme kinds."""

        CASHBACK = "cashback", _("Cashback")
        LOYALTY_POINTS = "loyalty_points", _("Loyalty points")
        MEMBERSHIP = "membership", _("Membership")
        SUBSCRIPTION = "subscription", _("Subscription")
        CARD_BENEFIT = "card_benefit", _("Card benefit")

    name = models.CharField(_("Name"), max_length=150, unique=True)
    kind = models.CharField(_("Kind"), max_length=20, choices=Kind)
    issuer_channel = models.ForeignKey(
        Channel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="programs",
        verbose_name=_("Issuing channel"),
    )
    issuer_seller = models.ForeignKey(
        SellerAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="programs",
        verbose_name=_("Issuing seller"),
    )
    issuer_name = models.CharField(
        _("Issuer"),
        max_length=150,
        blank=True,
        help_text=_("A bank, wallet or platform outside the catalog."),
    )
    market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="programs",
        verbose_name=_("Market"),
    )
    unit = models.CharField(
        _("Unit"),
        max_length=50,
        help_text=_("A currency code, or the name of the points it grants."),
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Program")
        verbose_name_plural = _("Programs")
        ordering = ("name",)
        constraints = (
            models.CheckConstraint(
                condition=Q(issuer_channel__isnull=False)
                | Q(issuer_seller__isnull=False)
                | ~Q(issuer_name=""),
                name="program_has_an_issuer",
            ),
        )

    def __str__(self) -> str:
        """Return the name."""
        return self.name
