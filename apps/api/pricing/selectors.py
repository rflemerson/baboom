"""What the public catalog reads from pricing: policies and projected prices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Case, F, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce, NullIf

from .models import BASE, BEST, OfferScenarioProjection, PricingPolicyRevision

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

    def lookups(self, *, applies_benefits: bool = True) -> dict[str, object]:
        """Choose the stored alternatives whose exact benefits fit the filter.

        Projections keep the best price per exact set of benefits, so
        requiring or excluding one reads the same offer's best price with
        what remains allowed; the cheapest fitting alternative that is still
        valid wins. Without a filter every alternative fits. A policy that
        applies no benefit stores only the store's price, which uses neither:
        it fits unless the filter requires one.
        """
        if not applies_benefits:
            allowed = self.uses_coupon is not True and self.has_cashback is not True
            return {} if allowed else {"alternative__in": []}
        if self.uses_coupon is None and self.has_cashback is None:
            return {}
        names = []
        for coupon in _choices(wanted=self.uses_coupon):
            for cashback in _choices(wanted=self.has_cashback):
                used = [
                    n for n, on in (("cashback", cashback), ("coupon", coupon)) if on
                ]
                names.append("+".join(used) or "none")
        if self.uses_coupon is not True and self.has_cashback is not True:
            names.append(BASE)
        return {"alternative__in": names}


def _choices(*, wanted: bool | None) -> tuple[bool, ...]:
    """Return the presence values a filter on one benefit allows."""
    return (False, True) if wanted is None else (wanted,)


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
    lookups = benefits.lookups(applies_benefits=policy.as_policy().apply_benefits)

    def source() -> QuerySet:
        return (
            OfferScenarioProjection.objects.filter(
                **lookups,
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
                search_status=F("optimization_status"),
                pricing_details=F("explanation"),
            )
            .order_by(
                "comparison_amount",
                "offer_id",
                Case(When(alternative=BEST, then=0), default=1),
            )
        )

    return source
