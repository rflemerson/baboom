"""Assemble the same engine inputs for contextual quotes and public projections."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .costs import CostBook
from .domain.engine import Inputs
from .domain.scopes import reaching
from .domain.types import CheckoutGroup

if TYPE_CHECKING:
    from .domain.types import PurchaseContext
    from .facts import Facts
    from .models import PricingPolicyRevision


@dataclass(frozen=True)
class Terms:
    """What a caller adds to the facts: tax regime, exact benefits, preloaded costs."""

    tax_inclusion: str = "unknown"
    benefits: frozenset[str] | None = None
    costs: CostBook | None = None

    def inputs(
        self,
        facts: Facts,
        policy: PricingPolicyRevision,
        context: PurchaseContext,
        *,
        group_key: str,
    ) -> Inputs:
        """Use explicit context and cost coverage without assuming eligibility."""
        ids = {line.offer_id for line in context.lines}
        if not context.groups:
            context = replace(
                context, groups=(CheckoutGroup(group_key, frozenset(ids)),)
            )
        keys = [group.key for group in context.groups]
        book = (
            self.costs if self.costs is not None else CostBook.load(keys, context.now)
        )
        shipping, fees, fees_status = book.for_groups(keys, self.tax_inclusion)
        return Inputs(
            context=context,
            offers=tuple(offer for offer in facts.offers.values() if offer.id in ids),
            prices=tuple(price for price in facts.prices if price.offer_id in ids),
            revisions=reaching(
                facts.revisions,
                (offer for offer in facts.offers.values() if offer.id in ids),
            ),
            policy=policy.as_policy(),
            routes=tuple(route for route in facts.routes if route.offer_id in ids),
            shipping=shipping,
            fees=fees,
            fees_status=fees_status,
            benefits=self.benefits,
        )
