"""Assemble the same engine inputs for contextual quotes and public projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .domain.engine import Inputs

if TYPE_CHECKING:
    from .costs import CostBook
    from .domain.types import Policy, PurchaseContext
    from .facts import Facts


@dataclass(frozen=True)
class Terms:
    """What a caller adds to the facts: loaded costs, tax regime, exact benefits.

    Assembling reads nothing: the caller loads the costs of its groups once,
    however many carts it then evaluates.
    """

    costs: CostBook
    tax_inclusion: str = "unknown"
    benefits: frozenset[str] | None = None

    def inputs(self, facts: Facts, policy: Policy, context: PurchaseContext) -> Inputs:
        """Use explicit context and cost coverage without assuming eligibility."""
        ids = {line.offer_id for line in context.lines}
        keys = [group.key for group in context.groups]
        shipping, fees, fees_status = self.costs.for_groups(keys, self.tax_inclusion)
        return Inputs(
            context=context,
            offers=facts.offers_of(ids),
            prices=facts.prices_of(ids),
            revisions=facts.revisions_reaching(ids),
            policy=policy,
            routes=facts.routes_of(ids),
            shipping=shipping,
            fees=fees,
            fees_status=fees_status,
            benefits=self.benefits,
        )
