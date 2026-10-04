"""Evaluate one purchase scenario: base prices, promotions, shipping, rewards.

``evaluate`` is a pure function. It takes every usable base price per line,
keeps the revisions that apply, builds the combinations compatibility
allows, applies each combination stage by stage, and returns the best
result under the policy's objective, with every decision explained.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .base_prices import base_choices, price_options
from .effects import (
    LineState,
)
from .money import ZERO
from .payments import payment_choices
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
        PaymentChoice,
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
        return empty_result(
            inputs, decisions, missing, assumptions, OptimizationStatus.COMPLETE
        )
    choices, cut = base_choices(options)
    if cut:
        assumptions.append("base prices limited to each line's cheapest")

    best: _Choice | None = None
    remaining = inputs.policy.max_combinations
    for selected in choices:
        for payment in payment_choices(inputs, selected):
            if remaining < 1:
                cut = True
                break
            found = _best_for_base(inputs, offers, list(selected), payment, remaining)
            remaining -= found.used
            cut = cut or found.cut
            if found.choice is not None and (
                best is None or found.choice.key < best.key
            ):
                best = found.choice
    if cut:
        assumptions.append("search limited to the combination budget")
    status = OptimizationStatus.BOUNDED if cut else OptimizationStatus.COMPLETE
    if best is None:
        decisions.append(
            Decision(
                "scenario",
                DecisionStatus.INELIGIBLE,
                f"no combination uses exactly {sorted(inputs.benefits or ())}",
            ),
        )
        return empty_result(inputs, decisions, missing, assumptions, status)
    outcome = best.outcome
    outcome.decisions[:0] = [*decisions, *best.decisions]
    outcome.missing[:0] = missing
    outcome.assumptions[:0] = [*assumptions, *best.assumptions]
    return build_result(inputs, best.selected, best.payment, outcome, status)


@dataclass
class _Choice:
    """The best combination of promotions for one base and one way to pay."""

    key: tuple[Decimal, Decimal, int, Decimal]
    selected: list[SelectedPrice]
    payment: PaymentChoice | None
    outcome: Outcome
    decisions: list[Decision]
    assumptions: list[str]


@dataclass
class _Searched:
    """What searching one base and payment found, cost and whether it was cut."""

    choice: _Choice | None
    used: int
    cut: bool


def _best_for_base(
    inputs: Inputs,
    offers: dict[int, OfferFact],
    selected: list[SelectedPrice],
    payment: PaymentChoice | None,
    budget: int,
) -> _Searched:
    """Apply every allowed combination of promotions to a base and a payment."""
    scoped = replace(inputs, context=replace(inputs.context, payment=payment))
    decisions: list[Decision] = []
    assumptions: list[str] = []
    lines = [
        LineState.start(line, offers[line.offer_id], price)
        for line, price in zip(scoped.context.lines, selected, strict=True)
    ]
    candidates = candidate_revisions(scoped, lines, decisions)
    subsets, status = combinations(candidates, decisions, assumptions, budget)
    cut = status is OptimizationStatus.BOUNDED
    best: Outcome | None = None
    best_key: tuple[Decimal, Decimal, int, Decimal] | None = None
    alone: dict[int, Outcome] = {}
    base = sum((price.amount for price in selected), ZERO)
    for subset in subsets:
        outcome = apply_combination(scoped, lines, subset)
        if len(subset) == 1:
            alone[subset[0].id] = outcome
        if not meets_benefits(scoped, outcome):
            continue
        key = (
            objective_amount(scoped, outcome),
            -total_money_rewards(outcome),
            -len(outcome.applied),
            base,
        )
        if best_key is None or key < best_key:
            best, best_key = outcome, key
    if best is None or best_key is None:
        return _Searched(None, len(subsets), cut)
    decisions += unapplied_decisions(candidates, best, alone)
    choice = _Choice(best_key, selected, payment, best, decisions, assumptions)
    return _Searched(choice, len(subsets), cut)
