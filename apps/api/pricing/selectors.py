"""What the public catalog reads from pricing: policies and projected prices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import F, OuterRef, Q

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


def projected_prices(
    policy: PricingPolicyRevision,
    now: datetime,
    *,
    country: str,
    currency: str,
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
                offer__product_store__product=OuterRef("pk"),
                policy=policy,
                status=OfferScenarioProjection.Status.PRICED,
                market__country=country,
                currency_id=currency,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .annotate(url=F("offer__url"))
            .order_by("amount", "offer_id")
        )

    return source
