"""Load facts and rules from the database, run the engine, persist quotes.

This is the only place the pure engine meets the ORM. It reads in batches,
turns rows into the engine's frozen inputs and, when asked, keeps a quote
with the snapshot that reproduces the result.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from commerce.models import Market
from offers.models import OfferPriceObservation
from promotions.models import PromotionRevision
from promotions.rules.conditions import leaves

from .context import Terms
from .costs import CostBook
from .domain.conditions import (
    DESTINATION_FACT,
    ConditionInput,
    leaf_key,
)
from .domain.conditions import evaluate as evaluate_conditions
from .domain.engine import Inputs, canonical, evaluate, fingerprint
from .domain.types import (
    CartLine,
    Claim,
    PricingResult,
    PurchaseContext,
    Tri,
)
from .groups import one_group, token
from .models import (
    PricingPolicyRevision,
    PricingQuote,
    QuoteLine,
)

if TYPE_CHECKING:
    from datetime import datetime

from .facts import EMPTY_AMOUNTS, FactLoader


@dataclass(frozen=True)
class QuoteRequest:
    """What a caller asks: these lines, under this policy, in this context."""

    lines: tuple[CartLine, ...]
    policy: PricingPolicyRevision
    context: dict[str, object] | None = None


class PricingService:
    """Evaluate scenarios against stored facts, and keep quotes when asked."""

    def __init__(self, loader: FactLoader | None = None) -> None:
        """Use the given loader, or the database one."""
        self.loader = loader or FactLoader()

    def inputs(self, request: QuoteRequest, now: datetime | None = None) -> Inputs:
        """Build the engine's inputs for one request."""
        moment = now or timezone.now()
        facts = self.loader.load(
            (line.offer_id for line in request.lines),
            request.policy,
        )
        first = facts.offers.get(request.lines[0].offer_id) if request.lines else None
        market = Market.objects.select_related("currency").get(
            pk=first.market_id if first else request.policy.market_id,
        )
        extra = dict(request.context or {})
        context = PurchaseContext(
            now=moment,
            market_id=market.pk,
            currency=market.currency_id,
            minor_unit=market.currency.minor_unit,
            lines=request.lines,
            **extra,
        )
        if not context.groups:
            context = replace(
                context,
                groups=one_group(request.lines, context.destination),
            )
        costs = CostBook.load([group.key for group in context.groups], moment)
        terms = Terms(costs=costs, tax_inclusion=market.tax_inclusion)
        return terms.inputs(facts, request.policy.as_policy(), context)

    def evaluate(
        self, request: QuoteRequest, now: datetime | None = None
    ) -> PricingResult:
        """Evaluate one request without persisting anything."""
        return evaluate(self.inputs(request, now))

    @transaction.atomic
    def quote(self, request: QuoteRequest, now: datetime | None = None) -> PricingQuote:
        """Evaluate and keep a quote whose snapshot reproduces the result."""
        inputs = self.inputs(request, now)
        result = evaluate(inputs)
        protected = PricingService.private_safe(inputs)
        quote = PricingQuote.objects.create(
            policy=request.policy,
            market_id=inputs.context.market_id,
            currency_id=inputs.context.currency,
            input_fingerprint=result.input_fingerprint,
            engine_version=result.engine_version,
            snapshot={
                "schema_version": 1,
                "inputs": canonical(protected),
                "result": canonical(result),
                "protected_fingerprint": fingerprint(protected),
            },
            merchandise_total=result.merchandise_total,
            total_payable=result.total_payable,
            evaluated_at=result.evaluated_at,
            expires_at=result.expires_at,
        )
        quote.revisions.set(
            PromotionRevision.objects.filter(pk__in=[r.id for r in inputs.revisions]),
        )
        quote.observations.set(
            OfferPriceObservation.objects.filter(
                pk__in=[p.observation_id for p in result.selected_prices],
            ),
        )
        discounts = PricingService._discounts_by_offer(result)
        selected = {price.offer_id: price for price in result.selected_prices}
        QuoteLine.objects.bulk_create(
            QuoteLine(
                quote=quote,
                offer_id=line.offer_id,
                quantity=line.quantity,
                base_amount=(
                    selected[line.offer_id].amount
                    if line.offer_id in selected
                    else None
                ),
                allocated_discount=discounts.get(line.offer_id, Decimal(0)),
            )
            for line in result.lines
            if line.offer_id in {offer.id for offer in inputs.offers}
        )
        return quote

    @staticmethod
    def _discounts_by_offer(result: PricingResult) -> dict[int, Decimal]:
        totals: dict[int, Decimal] = {}
        for adjustment in result.adjustments:
            for offer_id, amount in adjustment.allocations:
                totals[offer_id] = totals.get(offer_id, Decimal(0)) + amount
        return totals

    @staticmethod
    def private_safe(inputs: Inputs) -> Inputs:
        """Return inputs a quote may keep, which still reproduce its result.

        Codes become the same keyed token on both sides, so a code a buyer
        entered still matches the code a revision names, and neither is stored
        in clear. The postal code is replaced by a token after every destination
        leaf was evaluated with it; those outcomes travel as facts with their
        provenance, so a replay reaches the same decision without the address.
        """
        context = inputs.context
        facts = tuple(PricingService._destination_facts(inputs))
        destination = context.destination
        if destination is not None and destination.postal_code:
            destination = replace(
                destination, postal_code=token(destination.postal_code)
            )
        revisions = tuple(
            replace(
                revision,
                codes=tuple(
                    (kind, token(code) if code else code)
                    for kind, code in revision.codes
                ),
            )
            for revision in inputs.revisions
        )
        return replace(
            inputs,
            context=replace(
                context,
                destination=destination,
                codes=frozenset(token(code) for code in context.codes),
                claims=(*context.claims, *facts),
            ),
            revisions=revisions,
            prices=tuple(
                replace(
                    price,
                    context=tuple(
                        (
                            key,
                            token(value) if key == "postal_code" else value,
                        )
                        for key, value in price.context
                    ),
                )
                for price in inputs.prices
            ),
        )

    @staticmethod
    def _destination_facts(inputs: Inputs) -> list[Claim]:
        """Evaluate every destination leaf with the real destination, as facts."""
        facts: dict[str, Claim] = {}
        for revision in inputs.revisions:
            for leaf in PricingService._leaves_of_kind(
                revision.conditions.get("root"), "destination"
            ):
                outcome = evaluate_conditions(
                    {"root": leaf},
                    ConditionInput(
                        context=inputs.context,
                        revision=revision,
                        offers=inputs.offers,
                        qualifying=EMPTY_AMOUNTS,
                        order=EMPTY_AMOUNTS,
                    ),
                ).value
                if outcome is not Tri.UNKNOWN:
                    key = leaf_key(leaf)
                    facts[key] = Claim(
                        kind=DESTINATION_FACT,
                        issuer=key,
                        value=outcome is Tri.TRUE,
                        provenance="evaluated_before_protection",
                    )
        return list(facts.values())

    @staticmethod
    def _leaves_of_kind(node: object, kind: str) -> list[dict]:
        return [leaf for leaf in leaves(node) if leaf.get("kind") == kind]
