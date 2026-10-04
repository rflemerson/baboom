"""Recompute what the ranking reads: each linked offer under each public policy.

Projections are disposable. A refresh evaluates every offer alone, in its own
market, under every published public policy, and replaces the rows. Facts are
loaded once per refresh, not per offer.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from .models import OfferScenarioProjection, PricingPolicyRevision
from .services import PricingService

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

    def requirements(self) -> list[frozenset[str]]:
        """Return the winner, then each benefit and their union the policy allows."""
        benefits = []
        if self.codes:
            benefits.append("coupon")
        if self.policy.allow_rewards:
            benefits.append("cashback")
        requirements = [frozenset()]
        requirements += [frozenset({name}) for name in benefits]
        if len(benefits) > 1:
            requirements.append(frozenset(benefits))
        return requirements


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
                [
                    PricingService.group_fingerprint((CartLine(pk, 1),), None)
                    for pk in ids
                ],
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
        """Project the winner and the best alternative using each benefit.

        A buyer filtering for a coupon or cashback sees the best combination
        that uses it, even where a combination without it wins by default.
        An alternative that cannot be met is not stored.
        """
        rows = []
        for requirement in batch.requirements():
            row = self._projection(offer_id, batch, requirement)
            if requirement and row.status != OfferScenarioProjection.Status.PRICED:
                continue
            rows.append(row)
        return rows

    def _projection(
        self,
        offer_id: int,
        batch: _Batch,
        requirement: frozenset[str],
    ) -> OfferScenarioProjection:
        """Evaluate one offer alone and describe the result for the ranking."""
        facts, policy = batch.facts, batch.policy
        offer = facts.offers[offer_id]
        market = batch.markets[offer.market_id]
        context = PurchaseContext(
            now=batch.moment,
            market_id=market.pk,
            currency=market.currency_id,
            minor_unit=market.currency.minor_unit,
            lines=(CartLine(offer_id, 1),),
            codes=batch.codes,
        )
        result = evaluate(
            Terms(
                tax_inclusion=market.tax_inclusion,
                requirement=requirement,
                costs=batch.costs,
            ).inputs(
                facts,
                batch.policy_row,
                context,
                group_key=PricingService.group_fingerprint(
                    context.lines, context.destination
                ),
            ),
        )
        applied = [r for r in facts.revisions if r.id in result.applied_revisions]
        route = result.purchase_routes[0] if result.purchase_routes else None
        return OfferScenarioProjection(
            offer_id=offer_id,
            alternative="+".join(sorted(requirement)) or "best",
            policy=batch.policy_row,
            market=market,
            currency_id=market.currency_id,
            amount=result.merchandise_total,
            status=self._status(result, purchasable=offer.purchasable),
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
            comparison_amount=self._comparison(result, policy.objective),
            objective=policy.objective,
            total_payable=result.total_payable,
            estimated_net_cost=result.estimated_net_cost,
            monetary_reward=sum(
                (
                    reward.amount
                    for reward in result.deferred_rewards
                    if reward.credited_as == "money" and reward.amount is not None
                ),
                Decimal(0),
            ),
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
