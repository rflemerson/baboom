"""What pricing persists: policies, quotes, and the projections ranking reads.

A policy revision is immutable once published, like a promotion revision. A
quote keeps the snapshot of everything it used, so its explanation survives
any later edit. Shipping, tax and conversion quotes are observations or
adapter results; nothing here invents a freight or tax engine.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.models import BaseModel

from .domain.types import OptimizationStatus, Policy

if TYPE_CHECKING:
    from collections.abc import Callable

MONEY = {"max_digits": 19, "decimal_places": 6}


DEFAULT_FRESHNESS_HOURS = 72
# Stored alternatives that are not an exact set of benefits: the winner, and
# the store's price with no promotion at all.
BEST = "best"
BASE = "base"
OBJECTIVES = frozenset({"items_payable", "total_payable", "estimated_net_cost"})


def _objective(value: object) -> bool:
    return isinstance(value, str) and value in OBJECTIVES


def _flag(value: object) -> bool:
    return isinstance(value, bool)


def _names(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _positive(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


RULES: dict[str, tuple[Callable[[object], bool], str]] = {
    "objective": (_objective, f"one of {sorted(OBJECTIVES)}"),
    "apply_benefits": (_flag, "true or false"),
    "accepted_semantics": (_names, "a list of names"),
    "accepted_evidence": (_names, "a list of names"),
    "cash_methods": (_names, "a list of names"),
    "include_unknown_payment": (_flag, "true or false"),
    "allow_codes": (_flag, "true or false"),
    "auto_public_codes": (_flag, "true or false"),
    "allow_private_codes": (_flag, "true or false"),
    "allow_rewards": (_flag, "true or false"),
    "allow_conditions": (_names, "a list of names"),
    "net_cost_counts_money_rewards": (_flag, "true or false"),
    "assume_full_caps": (_flag, "true or false"),
    "max_combinations": (_positive, "a positive integer"),
    "freshness_hours": (_positive, "a positive integer"),
}


def rule_errors(rules: object) -> list[str]:
    """Return what is wrong with a policy's rules; empty when they are valid."""
    if not isinstance(rules, dict):
        return ["rules must be an object"]
    errors = [f"unknown rule {key!r}" for key in sorted(set(rules) - set(RULES))]
    for key, value in sorted(rules.items()):
        check = RULES.get(key)
        if check is not None and not check[0](value):
            errors.append(f"{key} must be {check[1]}, not {value!r}")
    return errors


# The rules the engine's Policy reads; freshness is read by the fact loader.
POLICY_FIELDS = tuple(key for key in RULES if key != "freshness_hours")


class PricingPolicyRevision(BaseModel):
    """What one public scenario counts, in one market, from one version on.

    ``rules`` is the typed policy the engine reads: accepted price meanings
    and evidence, the cash methods, whether codes, conditions and rewards
    count, the freshness of each source and the search bound.
    """

    key = models.SlugField(_("Key"), max_length=50)
    number = models.PositiveIntegerField(_("Number"))
    market = models.ForeignKey(
        "commerce.Market",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pricing_policies",
        verbose_name=_("Market"),
        help_text=_("Empty for a policy every market uses."),
    )
    scenario = models.CharField(
        _("Scenario"),
        max_length=10,
        choices=[
            ("listed", _("The store's price")),
            ("best", _("The best price paid now")),
            ("cash", _("Paid at once")),
            ("payment", _("A payment method")),
        ],
    )
    rules = models.JSONField(_("Rules"), default=dict, blank=True)
    is_default = models.BooleanField(
        _("Default ranking"),
        default=False,
        help_text=_("The scenario the public catalog ranks by when none is chosen."),
    )
    published_at = models.DateTimeField(_("Published At"), null=True, blank=True)
    content_hash = models.CharField(_("Content Hash"), max_length=64, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Pricing Policy Revision")
        verbose_name_plural = _("Pricing Policy Revisions")
        ordering = ("key", "-number")
        constraints = (
            models.UniqueConstraint(
                fields=("key", "number"),
                name="unique_policy_revision",
            ),
        )

    def __str__(self) -> str:
        """Return key and number."""
        return f"{self.key} v{self.number}"

    def clean(self) -> None:
        """Refuse rules the engine would misread; checked before publishing."""
        errors = rule_errors(self.rules)
        if errors:
            raise ValidationError({"rules": errors})

    def as_policy(self) -> Policy:
        """Read the typed rules the engine applies; unknown keys are ignored."""
        rules = self.rules or {}
        values: dict[str, object] = {}
        for name in POLICY_FIELDS:
            if name in rules:
                value = rules[name]
                values[name] = frozenset(value) if isinstance(value, list) else value
        return Policy(
            key=self.key, version=self.number, scenario=self.scenario, **values
        )

    @property
    def freshness(self) -> timedelta:
        """How long an observation stays usable after a read confirmed it."""
        hours = (self.rules or {}).get("freshness_hours", DEFAULT_FRESHNESS_HOURS)
        return timedelta(hours=int(hours))

    def save(self, *args: object, **kwargs: object) -> None:
        """Refuse changes to a published policy; publish a new number instead."""
        self.rules = self.rules or {}
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).first()
            if stored is not None and stored.published_at is not None:
                changed = [
                    field.attname
                    for field in self._meta.concrete_fields
                    if field.attname not in self.MUTABLE_WHEN_PUBLISHED
                    and getattr(stored, field.attname) != getattr(self, field.attname)
                ]
                if changed:
                    msg = "A published policy cannot change; publish a new number."
                    raise ValueError(msg)
        super().save(*args, **kwargs)

    MUTABLE_WHEN_PUBLISHED = frozenset({"is_default", "updated_at"})

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        """Refuse to delete a published policy; its quotes refer to it."""
        if self.published_at is not None:
            msg = "A published policy is kept; publish a new number instead."
            raise ValueError(msg)
        return super().delete(*args, **kwargs)


class PricingQuote(BaseModel):
    """One evaluated scenario, with the snapshot that reproduces it.

    The context fingerprint never carries a postal code or a code in clear.
    """

    policy = models.ForeignKey(
        PricingPolicyRevision,
        on_delete=models.PROTECT,
        related_name="quotes",
        verbose_name=_("Policy"),
    )
    market = models.ForeignKey(
        "commerce.Market",
        on_delete=models.PROTECT,
        related_name="pricing_quotes",
        verbose_name=_("Market"),
    )
    currency = models.ForeignKey(
        "commerce.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Currency"),
    )
    input_fingerprint = models.CharField(_("Input Fingerprint"), max_length=64)
    engine_version = models.CharField(_("Engine Version"), max_length=20)
    snapshot = models.JSONField(
        _("Snapshot"),
        help_text=_("Every input the engine read and the result it returned."),
    )
    revisions = models.ManyToManyField(
        "promotions.PromotionRevision",
        related_name="quotes",
        verbose_name=_("Revisions read"),
    )
    observations = models.ManyToManyField(
        "offers.OfferPriceObservation",
        related_name="quotes",
        verbose_name=_("Observations read"),
    )
    merchandise_total = models.DecimalField(_("Merchandise"), null=True, **MONEY)
    total_payable = models.DecimalField(_("Total Payable"), null=True, **MONEY)
    evaluated_at = models.DateTimeField(_("Evaluated At"))
    expires_at = models.DateTimeField(_("Expires At"), null=True, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Pricing Quote")
        verbose_name_plural = _("Pricing Quotes")
        ordering = ("-evaluated_at",)
        indexes = (models.Index(fields=["input_fingerprint"]),)

    def __str__(self) -> str:
        """Return the policy, total and moment."""
        total = self.total_payable if self.total_payable is not None else "?"
        moment = f"{self.evaluated_at:%d/%m %H:%M}"
        return f"{self.policy} {self.currency_id} {total} @ {moment}"

    def save(self, *args: object, **kwargs: object) -> None:
        """Write a quote once; refuse to rewrite it."""
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            msg = "A quote is immutable."
            raise ValueError(msg)
        super().save(*args, **kwargs)


class QuoteLine(BaseModel):
    """One offer of a quote, queryable without reading the snapshot."""

    quote = models.ForeignKey(
        PricingQuote,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("Quote"),
    )
    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.PROTECT,
        related_name="quote_lines",
        verbose_name=_("Offer"),
    )
    quantity = models.PositiveIntegerField(_("Quantity"))
    base_amount = models.DecimalField(
        _("Base Amount"),
        null=True,
        blank=True,
        help_text=_("Empty when the line had no price in the scenario."),
        **MONEY,
    )
    allocated_discount = models.DecimalField(
        _("Allocated Discount"),
        default=0,
        **MONEY,
    )

    class Meta:
        """Meta options."""

        verbose_name = _("Quote Line")
        verbose_name_plural = _("Quote Lines")

    def __str__(self) -> str:
        """Return offer and quantity."""
        return f"{self.quantity} x {self.offer_id}"


class ShippingQuote(BaseModel):
    """A shipping price for one group, seller and destination, as quoted.

    The destination is kept coarse; the postal code only as a hash. Quantity,
    value and modality are part of the quote, not just offer and postcode.
    """

    group_fingerprint = models.CharField(_("Group Fingerprint"), max_length=64)
    seller_account = models.ForeignKey(
        "commerce.SellerAccount",
        on_delete=models.PROTECT,
        related_name="shipping_quotes",
        verbose_name=_("Seller Account"),
    )
    country = models.CharField(_("Country"), max_length=2)
    subdivision = models.CharField(_("Subdivision"), max_length=10, blank=True)
    postal_code_hash = models.CharField(_("Postal Code Hash"), max_length=64)
    modality = models.CharField(_("Modality"), max_length=100, blank=True)
    external_quote_id = models.CharField(
        _("External Quote ID"),
        max_length=200,
        blank=True,
        help_text=_("The carrier's id for this quote, when it can be booked by id."),
    )
    execution_guaranteed = models.BooleanField(
        _("Execution guaranteed"),
        default=False,
        help_text=_("The source honours this quote by id until it expires."),
    )
    order_value = models.DecimalField(
        _("Order Value"),
        null=True,
        blank=True,
        help_text=_("The order value priced, when shipping depends on it."),
        **MONEY,
    )
    packages = models.JSONField(_("Packages"), default=list, blank=True)
    amount = models.DecimalField(_("Amount"), null=True, blank=True, **MONEY)
    currency = models.ForeignKey(
        "commerce.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Currency"),
    )
    estimate_days = models.PositiveIntegerField(
        _("Estimate (days)"), null=True, blank=True
    )
    source = models.CharField(_("Source"), max_length=100)
    included_benefits = models.JSONField(
        _("Included Benefits"), default=list, blank=True
    )
    observed_at = models.DateTimeField(_("Observed At"), default=timezone.now)
    expires_at = models.DateTimeField(_("Expires At"))

    class Meta:
        """Meta options."""

        verbose_name = _("Shipping Quote")
        verbose_name_plural = _("Shipping Quotes")
        ordering = ("-observed_at",)
        indexes = (models.Index(fields=["group_fingerprint", "-observed_at"]),)
        constraints = (
            models.CheckConstraint(
                condition=Q(amount__isnull=True) | Q(amount__gte=0),
                name="shipping_amount_not_negative",
            ),
        )

    def __str__(self) -> str:
        """Return modality and amount."""
        return f"{self.modality or self.source} {self.currency_id} {self.amount}"


class TaxFeeQuote(BaseModel):
    """A tax or fee for one group: its base, amount and whether a price holds it."""

    group_fingerprint = models.CharField(_("Group Fingerprint"), max_length=64)
    kind = models.CharField(_("Kind"), max_length=50)
    charge_key = models.CharField(
        _("Charge Key"),
        max_length=200,
        blank=True,
        help_text=_("Tells two charges of one kind apart; rereadings share it."),
    )
    covers_all_charges = models.BooleanField(
        _("Covers every charge"),
        default=False,
        help_text=_(
            "The source answered for every charge of the group in this reading; "
            "a row of kind 'none' and amount 0 confirms there is none.",
        ),
    )
    base = models.DecimalField(_("Base"), null=True, blank=True, **MONEY)
    amount = models.DecimalField(_("Amount"), null=True, blank=True, **MONEY)
    currency = models.ForeignKey(
        "commerce.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Currency"),
    )
    inclusion = models.CharField(
        _("Inclusion"),
        max_length=8,
        choices=[
            ("included", _("Included in the price")),
            ("excluded", _("Charged on top")),
            ("unknown", _("Unknown")),
        ],
    )
    source = models.CharField(_("Source"), max_length=100)
    observed_at = models.DateTimeField(_("Observed At"), default=timezone.now)
    expires_at = models.DateTimeField(_("Expires At"))

    class Meta:
        """Meta options."""

        verbose_name = _("Tax or Fee Quote")
        verbose_name_plural = _("Tax and Fee Quotes")

    def __str__(self) -> str:
        """Return kind and amount."""
        return f"{self.kind} {self.currency_id} {self.amount}"


class OfferScenarioProjection(BaseModel):
    """An offer's amount under one public policy, read by the ranking.

    Projections are disposable: recomputed from facts and rules, never edited.
    ``status`` is ``priced`` only when the engine produced a merchandise
    amount; anything else keeps the reason and no amount.
    """

    class Status(models.TextChoices):
        """Whether the offer has a price in the scenario."""

        PRICED = "priced", _("Priced")
        NO_PRICE = "no_price", _("No price in this scenario")
        UNAVAILABLE = "unavailable", _("Not purchasable")

    offer = models.ForeignKey(
        "offers.Offer",
        on_delete=models.CASCADE,
        related_name="projections",
        verbose_name=_("Offer"),
    )
    policy = models.ForeignKey(
        PricingPolicyRevision,
        on_delete=models.CASCADE,
        related_name="projections",
        verbose_name=_("Policy"),
    )
    market = models.ForeignKey(
        "commerce.Market",
        on_delete=models.CASCADE,
        related_name="projections",
        verbose_name=_("Market"),
    )
    currency = models.ForeignKey(
        "commerce.Currency",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("Currency"),
    )
    amount = models.DecimalField(_("Amount"), null=True, blank=True, **MONEY)
    status = models.CharField(_("Status"), max_length=12, choices=Status)
    payment_method = models.CharField(_("Payment Method"), max_length=50, blank=True)
    observation = models.ForeignKey(
        "offers.OfferPriceObservation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projections",
        verbose_name=_("Observation"),
    )
    alternative = models.CharField(
        _("Alternative"),
        max_length=40,
        default="best",
        help_text=_(
            "'best' is the winning combination; 'none', 'coupon', 'cashback' and "
            "'cashback+coupon' are the best combinations using exactly those "
            "benefits; 'base' is the price with no promotion. All are kept so "
            "a filter or an expired promotion never hides a valid option.",
        ),
    )
    comparison_amount = models.DecimalField(null=True, blank=True, **MONEY)
    optimization_status = models.CharField(
        _("Optimization status"),
        max_length=10,
        choices=[(status.value, status.value) for status in OptimizationStatus],
        default=OptimizationStatus.COMPLETE,
        help_text=_(
            "'bounded' when the search stopped before covering every base price, "
            "payment and combination of promotions: the amount may not be the "
            "cheapest, or an alternative may exist that was not found.",
        ),
    )
    objective = models.CharField(max_length=30, default="items_payable")
    total_payable = models.DecimalField(null=True, blank=True, **MONEY)
    estimated_net_cost = models.DecimalField(null=True, blank=True, **MONEY)
    monetary_reward = models.DecimalField(null=True, blank=True, **MONEY)
    uses_coupon = models.BooleanField(default=False, db_index=True)
    has_cashback = models.BooleanField(default=False, db_index=True)
    selected_route_id = models.PositiveBigIntegerField(null=True, blank=True)
    resolved_url = models.URLField(max_length=2000, blank=True)
    link_fixes_variant = models.BooleanField(default=False)
    explanation = models.JSONField(_("Explanation"), default=dict, blank=True)
    link_fixes_seller = models.BooleanField(
        _("Link opens this seller"),
        default=True,
        help_text=_("False when the offer's link may open another seller's offer."),
    )
    fingerprint = models.CharField(_("Fingerprint"), max_length=64)
    computed_at = models.DateTimeField(_("Computed At"))
    expires_at = models.DateTimeField(_("Expires At"), null=True, blank=True)

    class Meta:
        """Meta options."""

        verbose_name = _("Offer Scenario Projection")
        verbose_name_plural = _("Offer Scenario Projections")
        constraints = (
            models.UniqueConstraint(
                fields=("offer", "policy", "alternative"),
                name="one_projection_per_offer_policy_alternative",
            ),
            models.CheckConstraint(
                condition=Q(status="priced", amount__isnull=False)
                | (~Q(status="priced") & Q(amount__isnull=True)),
                name="priced_projection_has_amount",
            ),
        )
        indexes = (
            models.Index(fields=["policy", "status", "amount"]),
            models.Index(fields=["policy", "expires_at"]),
        )

    def __str__(self) -> str:
        """Return offer, policy and amount."""
        return f"{self.offer_id} {self.policy} {self.amount or self.status}"
