"""Evaluate one purchase scenario: base prices, promotions, shipping, rewards.

``evaluate`` is a pure function. It takes every usable base price per line,
keeps the revisions that apply, builds the combinations compatibility
allows, applies each combination stage by stage, and returns the best
result under the policy's objective, with every decision explained.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base_prices import base_choices, price_options
from .effects import (
    LineState,
)
from .money import ZERO
from .types import (
    Decision,
    DecisionStatus,
    OptimizationStatus,
    PricingResult,
    SelectedPrice,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from .inputs import Inputs
    from .types import (
        OfferFact,
    )
from .application import (
    Outcome,
    apply_combination,
    meets_benefits,
    objective_amount,
    total_money_rewards,
    unapplied_decisions,
)
from .candidates import candidate_revisions
from .results import build_result, empty_result
from .search import combinations


def evaluate(inputs: Inputs) -> PricingResult:
    """Return the scenario's result for these inputs and this ``now``."""
    decisions: list[Decision] = []
    missing: list[str] = []
    assumptions: list[str] = []
    offers = {offer.id: offer for offer in inputs.offers}

    options = price_options(inputs, offers, decisions, missing)
    if options is None:
        return empty_result(inputs, decisions, missing, assumptions)
    choices, bounded = base_choices(options)
    if bounded:
        assumptions.append("base prices limited to each line's cheapest")

    best: _Choice | None = None
    for selected in choices:
        choice = _best_for_base(inputs, offers, list(selected))
        if choice is not None and (best is None or choice.key < best.key):
            best = choice
    if best is None:
        decisions.append(
            Decision(
                "scenario",
                DecisionStatus.INELIGIBLE,
                f"no combination uses exactly {sorted(inputs.benefits or ())}",
            ),
        )
        return empty_result(inputs, decisions, missing, assumptions)
    outcome = best.outcome
    outcome.decisions[:0] = [*decisions, *best.decisions]
    outcome.missing[:0] = missing
    outcome.assumptions[:0] = [*assumptions, *best.assumptions]
    return build_result(inputs, best.selected, outcome, best.status)


@dataclass
class _Choice:
    """The best combination of promotions for one choice of base prices."""

    key: tuple[Decimal, Decimal, int, Decimal]
    selected: list[SelectedPrice]
    outcome: Outcome
    status: OptimizationStatus
    decisions: list[Decision]
    assumptions: list[str]


def _best_for_base(
    inputs: Inputs,
    offers: dict[int, OfferFact],
    selected: list[SelectedPrice],
) -> _Choice | None:
    """Apply every allowed combination of promotions to these base prices."""
    decisions: list[Decision] = []
    assumptions: list[str] = []
    lines = [
        LineState.start(line, offers[line.offer_id], price)
        for line, price in zip(inputs.context.lines, selected, strict=True)
    ]
    candidates = candidate_revisions(inputs, lines, decisions)
    subsets, status = combinations(candidates, inputs.policy, decisions, assumptions)
    best: Outcome | None = None
    best_key: tuple[Decimal, Decimal, int, Decimal] | None = None
    alone: dict[int, Outcome] = {}
    base = sum((price.amount for price in selected), ZERO)
    for subset in subsets:
        outcome = apply_combination(inputs, lines, subset)
        if len(subset) == 1:
            alone[subset[0].id] = outcome
        if not meets_benefits(inputs, outcome):
            continue
        key = (
            objective_amount(inputs, outcome),
            -total_money_rewards(outcome),
            -len(outcome.applied),
            base,
        )
        if best_key is None or key < best_key:
            best, best_key = outcome, key
    if best is None or best_key is None:
        return None
    decisions += unapplied_decisions(candidates, best, alone)
    return _Choice(best_key, selected, best, status, decisions, assumptions)
