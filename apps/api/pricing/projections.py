"""Recompute what the ranking reads: each linked offer under each public policy.

Projections are disposable. A refresh evaluates every offer alone, in its own
market, under every published public policy, and replaces the rows. Facts are
loaded once per refresh, not per offer.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from commerce.models import Market
from offers.models import Offer

from .context import Terms
from .costs import CostBook
from .domain.engine import evaluate
from .domain.types import CartLine, PurchaseContext
from .facts import LEGACY_PRICE_ID, FactLoader, Facts
from .groups import group_fingerprint, one_group
from .models import BASE, BEST, OfferScenarioProjection, PricingPolicyRevision

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from .domain.types import Policy, PricingResult


@dataclass(frozen=True)
class _Refresh:
    """What every policy of one refresh shares: markets, clock and costs."""

    markets: dict[int, Market]
    moment: datetime
    costs: CostBook


@dataclass(frozen=True)
class _Batch:
    """What every projection of one policy in one refresh shares."""

    policy_row: PricingPolicyRevision
    policy: Policy
    facts: Facts
    markets: dict[int, Market]
    moment: datetime
    costs: CostBook
    codes: frozenset[str]

    def alternatives(self) -> list[str]:
        """Name the winner, each exact set of coupon and cashback, and the base.

        Every subset is kept, the empty one included, so a filter that
        requires or excludes a benefit finds the same offer's best price
        with exactly the benefits it allows. ``base`` is the store's price
        with no promotion at all: the price a read falls back to when the
        winner's promotion ended before the worker repriced the offer.
        """
        if not self.policy.apply_benefits:
            return [BEST]
        names = []
        if self.codes:
            names.append("coupon")
        if self.policy.allow_rewards:
            names.append("cashback")
        subsets = [
            _alternative(frozenset(chosen))
            for size in range(len(names) + 1)
            for chosen in itertools.combinations(names, size)
        ]
        return [BEST, *subsets, BASE]


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
        """Recompute the projections of these offers (all linked ones by default).

        Offers are locked for the refresh, so two refreshes of one offer run
        one after the other; a refresh never replaces rows computed after its
        own ``now``, so an older run cannot overwrite a newer one.
        """
        moment = now or timezone.now()
        ids = sorted(set(offer_ids) if offer_ids is not None else self.linked_offers())
        if not ids:
            return 0
        list(Offer.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
        shared = _Refresh(
            markets=self._markets(ids),
            moment=moment,
            costs=CostBook.load(
                [group_fingerprint((CartLine(pk, 1),), None) for pk in ids],
                moment,
            ),
        )
        written = 0
        for policy_row in self.policies():
            batch = self._batch(policy_row, ids, shared)
            newer = set(
                OfferScenarioProjection.objects.filter(
                    policy=policy_row,
                    offer_id__in=ids,
                    computed_at__gt=moment,
                ).values_list("offer_id", flat=True),
            )
            eligible = [
                offer_id
                for offer_id in ids
                if offer_id not in newer
                and offer_id in batch.facts.offers
                and (
                    policy_row.market_id is None
                    or batch.facts.offers[offer_id].market_id == policy_row.market_id
                )
            ]
            OfferScenarioProjection.objects.filter(
                policy=policy_row,
                offer_id__in=[offer_id for offer_id in ids if offer_id not in newer],
            ).delete()
            rows = [
                row
                for offer_id in eligible
                for row in self._projections(offer_id, batch)
            ]
            OfferScenarioProjection.objects.bulk_create(rows)
            written += len(rows)
        return written

    def _batch(
        self,
        policy_row: PricingPolicyRevision,
        ids: list[int],
        shared: _Refresh,
    ) -> _Batch:
        policy = policy_row.as_policy()
        facts = self.loader.load(ids, policy_row)
        codes = (
            frozenset(
                code
                for revision in facts.revisions
                for kind, code in revision.codes
                if kind == "public_code" and code
            )
            if policy.allow_codes and policy.auto_public_codes
            else frozenset()
        )
        return _Batch(
            policy_row,
            policy,
            facts,
            shared.markets,
            shared.moment,
            shared.costs,
            codes,
        )

    def _projections(
        self, offer_id: int, batch: _Batch
    ) -> list[OfferScenarioProjection]:
        """Project the winner, each exact set of benefits and the base price.

        An alternative that cannot be met is not stored; neither is a base
        price equal to the ``none`` alternative, which applied no promotion.
        """
        rows: list[OfferScenarioProjection] = []
        for alternative in batch.alternatives():
            row = self._projection(offer_id, batch, alternative)
            if alternative != BEST and row.status != row.Status.PRICED:
                continue
            if alternative == BASE and not self._promoted(rows):
                continue
            rows.append(row)
        return rows

    @staticmethod
    def _promoted(rows: list[OfferScenarioProjection]) -> bool:
        """Tell whether the ``none`` alternative applied a promotion."""
        return any(
            row.alternative == "none" and (row.explanation or {}).get("applied")
            for row in rows
        )

    def _projection(
        self,
        offer_id: int,
        batch: _Batch,
        alternative: str,
    ) -> OfferScenarioProjection:
        """Evaluate one offer alone and describe the result for the ranking."""
        facts = batch.facts
        policy = (
            replace(batch.policy, apply_benefits=False)
            if alternative == BASE
            else batch.policy
        )
        offer = facts.offers[offer_id]
        market = batch.markets[offer.market_id]
        context = PurchaseContext(
            now=batch.moment,
            market_id=market.pk,
            currency=market.currency_id,
            minor_unit=market.currency.minor_unit,
            lines=(CartLine(offer_id, 1),),
            groups=one_group((CartLine(offer_id, 1),), None),
            codes=batch.codes,
        )
        terms = Terms(
            costs=batch.costs,
            tax_inclusion=market.tax_inclusion,
            benefits=_benefits(alternative),
        )
        result = evaluate(terms.inputs(facts, policy, context))
        applied = [r for r in facts.revisions if r.id in result.applied_revisions]
        route = result.purchase_routes[0] if result.purchase_routes else None
        reward = sum(
            (
                item.amount
                for item in result.deferred_rewards
                if item.credited_as == "money" and item.amount is not None
            ),
            Decimal(0),
        )
        return OfferScenarioProjection(
            offer_id=offer_id,
            alternative=alternative,
            policy=batch.policy_row,
            market=market,
            currency_id=market.currency_id,
            amount=result.merchandise_total,
            status=self._status(result, purchasable=offer.purchasable),
            payment_method=result.payment.method if result.payment else "",
            observation_id=(
                result.selected_prices[0].observation_id
                if result.selected_prices
                and result.selected_prices[0].observation_id != LEGACY_PRICE_ID
                else None
            ),
            comparison_amount=self._comparison(result, policy.objective),
            optimization_status=result.optimization_status,
            objective=policy.objective,
            total_payable=result.total_payable,
            estimated_net_cost=result.estimated_net_cost,
            monetary_reward=reward,
            uses_coupon=any(
                code in batch.codes for r in applied for _kind, code in r.codes
            ),
            has_cashback=any(
                reward.credited_as == "money" and reward.amount is not None
                for reward in result.deferred_rewards
            ),
            selected_route_id=route.route_id if route else None,
            resolved_url=(route.url or "") if route else "",
            link_fixes_variant=bool(route and route.fixes_variant),
            explanation={
                **self._explanation(result),
                "objective": policy.objective,
                "cashback": str(reward) if reward else None,
                "public_codes": sorted(
                    {
                        code
                        for r in applied
                        for kind, code in r.codes
                        if kind == "public_code" and code in batch.codes
                    },
                ),
            },
            link_fixes_seller=all(r.fixes_seller for r in result.purchase_routes),
            fingerprint=result.input_fingerprint,
            computed_at=batch.moment,
            expires_at=result.expires_at,
        )

    @staticmethod
    def policies() -> list[PricingPolicyRevision]:
        """Return the newest published revision of each public policy key."""
        newest: dict[str, PricingPolicyRevision] = {}
        published = PricingPolicyRevision.objects.filter(
            published_at__isnull=False,
        ).order_by("key", "-number")
        for policy in published:
            newest.setdefault(policy.key, policy)
        return list(newest.values())

    @staticmethod
    def linked_offers(
        store_slug: str | None = None,
        offer_ids: Iterable[int] | None = None,
    ) -> list[int]:
        """Return the offers some catalog product is priced by, optionally narrowed."""
        linked = Offer.objects.filter(product_store__isnull=False)
        if store_slug:
            linked = linked.filter(store_slug=store_slug)
        if offer_ids is not None:
            linked = linked.filter(pk__in=list(offer_ids))
        return list(linked.values_list("pk", flat=True).distinct())

    @staticmethod
    def _comparison(result: PricingResult, objective: str) -> Decimal | None:
        """Return the amount the policy's objective compares; unknown stays None."""
        if objective == "items_payable":
            return result.merchandise_total
        return getattr(result, objective, None)

    @staticmethod
    def _markets(ids: list[int]) -> dict[int, Market]:
        """Index the markets of these offers, with their currencies."""
        namespaces = set(
            Offer.objects.filter(pk__in=ids).values_list("store_slug", flat=True),
        )
        rows = Market.objects.select_related("currency").filter(
            listings__variants__offers__pk__in=ids,
        ) | Market.objects.select_related("currency").filter(namespace__in=namespaces)
        return {market.pk: market for market in rows.distinct()}

    @staticmethod
    def _status(result: PricingResult, *, purchasable: bool) -> str:
        if result.merchandise_total is not None:
            return OfferScenarioProjection.Status.PRICED
        if not purchasable:
            return OfferScenarioProjection.Status.UNAVAILABLE
        return OfferScenarioProjection.Status.NO_PRICE

    @staticmethod
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
            "refusals": [
                f"{decision.subject}: {decision.status} ({decision.reason})"
                for decision in result.decisions
                if decision.subject.startswith(("price", "offer", "scenario"))
            ],
            "route_limitations": list(result.route_limitations),
            "routes": [
                {
                    "id": route.route_id,
                    "url": route.url,
                    "fixes_variant": route.fixes_variant,
                    "instructions": route.instructions,
                }
                for route in result.purchase_routes
            ],
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


def _alternative(benefits: frozenset[str]) -> str:
    """Name an exact set of benefits: "none", or its names joined."""
    return "+".join(sorted(benefits)) or "none"


def _benefits(alternative: str) -> frozenset[str] | None:
    """Return the exact benefits a stored alternative asks the engine for."""
    if alternative == BEST:
        return None
    if alternative in {"none", BASE}:
        return frozenset()
    return frozenset(alternative.split("+"))
