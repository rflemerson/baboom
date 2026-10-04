"""Recompute what the ranking reads: each linked offer under each public policy.

Projections are disposable. A refresh evaluates every offer alone, in its own
market, under every published public policy, and replaces the rows. Facts are
loaded once per refresh, not per offer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from commerce.models import Market
from core.models import ProductStore
from offers.models import Offer

from .domain.engine import Inputs, evaluate
from .domain.types import CartLine, PurchaseContext
from .models import OfferScenarioProjection, PricingPolicyRevision
from .services import LEGACY_PRICE_ID, FactLoader, Facts, policy_from

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from .domain.types import PricingResult


def public_policies() -> list[PricingPolicyRevision]:
    """Return the newest published revision of each public policy key."""
    newest: dict[str, PricingPolicyRevision] = {}
    published = PricingPolicyRevision.objects.filter(
        published_at__isnull=False,
    ).order_by("key", "-number")
    for policy in published:
        newest.setdefault(policy.key, policy)
    return list(newest.values())


def linked_offer_ids() -> list[int]:
    """Return the offers some catalog product is priced by."""
    return list(
        ProductStore.objects.filter(offer__isnull=False).values_list(
            "offer_id",
            flat=True,
        ),
    )


class ProjectionService:
    """Evaluate offers alone under each public policy and store the result."""

    def __init__(self, loader: FactLoader | None = None) -> None:
        """Use the given loader, or the database one."""
        self.loader = loader or FactLoader()

    @transaction.atomic
    def refresh(
        self,
        offer_ids: Iterable[int] | None = None,
        now: datetime | None = None,
    ) -> int:
        """Recompute the projections of these offers (all linked ones by default)."""
        moment = now or timezone.now()
        ids = sorted(set(offer_ids) if offer_ids is not None else linked_offer_ids())
        if not ids:
            return 0
        written = 0
        markets = _markets(ids)
        for policy_row in public_policies():
            facts = self.loader.load(ids, policy_row)
            OfferScenarioProjection.objects.filter(
                policy=policy_row,
                offer_id__in=ids,
            ).delete()
            rows = [
                self._projection(offer_id, policy_row, facts, markets, moment)
                for offer_id in ids
                if offer_id in facts.offers
                and (
                    policy_row.market_id is None
                    or facts.offers[offer_id].market_id == policy_row.market_id
                )
            ]
            OfferScenarioProjection.objects.bulk_create(rows)
            written += len(rows)
        return written

    @staticmethod
    def _projection(
        offer_id: int,
        policy_row: PricingPolicyRevision,
        facts: Facts,
        markets: dict[int, Market],
        moment: datetime,
    ) -> OfferScenarioProjection:
        """Evaluate one offer alone and describe the result for the ranking."""
        offer = facts.offers[offer_id]
        market = markets[offer.market_id]
        result = evaluate(
            Inputs(
                context=PurchaseContext(
                    now=moment,
                    market_id=market.pk,
                    currency=market.currency_id,
                    minor_unit=market.currency.minor_unit,
                    lines=(CartLine(offer_id, 1),),
                ),
                offers=(offer,),
                prices=tuple(p for p in facts.prices if p.offer_id == offer_id),
                revisions=facts.revisions,
                policy=policy_from(policy_row),
                routes=tuple(r for r in facts.routes if r.offer_id == offer_id),
            ),
        )
        return OfferScenarioProjection(
            offer_id=offer_id,
            policy=policy_row,
            market=market,
            currency_id=market.currency_id,
            amount=result.merchandise_total,
            status=_status(result, purchasable=offer.purchasable),
            payment_method=(
                result.selected_prices[0].payment_method
                if result.selected_prices
                else ""
            ),
            observation_id=(
                result.selected_prices[0].observation_id
                if result.selected_prices
                and result.selected_prices[0].observation_id != LEGACY_PRICE_ID
                else None
            ),
            explanation=_explanation(result),
            link_fixes_seller=all(
                route.fixes_seller for route in result.purchase_routes
            ),
            fingerprint=result.input_fingerprint,
            computed_at=moment,
            expires_at=result.expires_at,
        )


def _markets(ids: list[int]) -> dict[int, Market]:
    """Index the markets of these offers, with their currencies."""
    namespaces = set(
        Offer.objects.filter(pk__in=ids).values_list("store_slug", flat=True),
    )
    rows = Market.objects.select_related("currency").filter(
        listings__variants__offers__pk__in=ids,
    ) | Market.objects.select_related("currency").filter(namespace__in=namespaces)
    return {market.pk: market for market in rows.distinct()}


def _status(result: PricingResult, *, purchasable: bool) -> str:
    if result.merchandise_total is not None:
        return OfferScenarioProjection.Status.PRICED
    if not purchasable:
        return OfferScenarioProjection.Status.UNAVAILABLE
    return OfferScenarioProjection.Status.NO_PRICE


def _explanation(result: PricingResult) -> dict[str, object]:
    """Keep what the catalog shows about how a projected amount was reached."""
    return {
        "scenario": result.scenario,
        "applied": list(result.applied_revisions),
        "adjustments": [
            {"kind": a.kind, "amount": str(a.amount), "revision": a.revision_id}
            for a in result.adjustments
        ],
        "missing": list(result.missing_context),
        "route_limitations": list(result.route_limitations),
        "assumptions": list(result.assumptions),
        "selected": [
            {
                "payment_method": p.payment_method,
                "payment_scope": p.payment_scope,
                "installments": p.installment_count,
                "already_included": list(p.already_included),
            }
            for p in result.selected_prices
        ],
    }
