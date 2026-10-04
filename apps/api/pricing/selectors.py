"""What the public catalog reads from pricing: policies and projected prices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import F, OuterRef, Q, Value
from django.db.models.functions import Coalesce, NullIf

from .models import OfferScenarioProjection, PricingPolicyRevision

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from django.db.models import QuerySet


def public_policy(key: str | None = None) -> PricingPolicyRevision | None:
    """Return the newest published revision of a policy, or the default one."""
    published = PricingPolicyRevision.objects.filter(published_at__isnull=False)
    chosen = published.filter(key=key) if key else published.filter(is_default=True)
    return chosen.order_by("-number").first()


@dataclass(frozen=True)
class BenefitFilter:
    """Filter calculated benefits before offer selection and pagination."""

    uses_coupon: bool | None = None
    has_cashback: bool | None = None

    def lookups(self) -> dict[str, object]:
        """Choose the projected alternative, then exclude what must be absent.

        Requiring a benefit reads the best alternative that uses it, so an
        offer whose winner skips the coupon is still found with it.
        Excluding a benefit keeps only alternatives that do not use it.
        """
        required = sorted(
            name
            for name, wanted in (
                ("cashback", self.has_cashback),
                ("coupon", self.uses_coupon),
            )
            if wanted
        )
        lookups: dict[str, object] = {"alternative": "+".join(required) or "best"}
        if self.uses_coupon is False:
            lookups["uses_coupon"] = False
        if self.has_cashback is False:
            lookups["has_cashback"] = False
        return lookups


DEFAULT_BENEFITS = BenefitFilter()


def projected_prices(
    policy: PricingPolicyRevision,
    now: datetime,
    *,
    country: str,
    currency: str,
    benefits: BenefitFilter = DEFAULT_BENEFITS,
) -> Callable[[], QuerySet]:
    """Return a price source over the projections of one policy in one market.

    The source yields, for the outer product, its offers priced under the
    policy in this country and currency and not expired, cheapest first, with
    ``amount``, ``url``, ``payment_method``, ``offer_id`` and ``expires_at``.
    Amounts of different currencies never compete. Ranking and pagination
    then run in the database.
    """

    def source() -> QuerySet:
        return (
            OfferScenarioProjection.objects.filter(
                **benefits.lookups(),
                comparison_amount__isnull=False,
                offer__product_store__product=OuterRef("pk"),
                policy=policy,
                status=OfferScenarioProjection.Status.PRICED,
                market__country=country,
                currency_id=currency,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .annotate(
                url=Coalesce(NullIf("resolved_url", Value("")), F("offer__url")),
                link_fixes=F("link_fixes_seller"),
                pricing_details=F("explanation"),
            )
            .order_by("comparison_amount", "offer_id")
        )

    return source
