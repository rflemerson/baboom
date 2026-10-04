"""Apply one combination of promotions stage by stage, and judge the outcome."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from .conditions import Amounts, ConditionInput
from .conditions import evaluate as evaluate_conditions
from .effects import (
    STAGES,
    Environment,
    LineState,
    apply_effect,
)
from .money import ZERO, round_money
from .scopes import qualifies, targets
from .types import (
    Decision,
    DecisionStatus,
    DeferredReward,
    Tri,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .inputs import Inputs
    from .types import (
        RevisionRule,
        RouteFact,
    )
from .charges import fee_total


@dataclass
class Outcome:
    """One combination applied."""

    lines: list[LineState]
    adjustments: list = field(default_factory=list)
    rewards: list[DeferredReward] = field(default_factory=list)
    gifts: list = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    applied: list[int] = field(default_factory=list)
    shipping: Decimal | None = None
    shipping_known: bool = False
    schedule_rates: tuple[Decimal, ...] = ()
    routes: dict[int, RouteFact] = field(default_factory=dict)
    tracking_programs: dict[int, set[int]] = field(default_factory=dict)


def apply_combination(
    inputs: Inputs,
    start: list[LineState],
    subset: tuple[RevisionRule, ...],
) -> Outcome:
    """Apply one combination stage by stage; conditions are read as they stand."""
    context = inputs.context
    lines = [line.copy() for line in start]
    outcome = Outcome(lines=lines)
    env = Environment(
        context,
        targets,
        inputs.policy.assume_full_caps,
        inputs.routes,
    )
    _shipping(inputs, outcome)
    initial = {line.offer.id: line.initial for line in lines}
    checkpoints: dict[str, dict[int, Decimal]] = {}
    held: dict[int, Tri] = {}
    for stage in STAGES:
        if stage == "shipping":
            _shipping(inputs, outcome)
        for revision, effect in _ordered(subset, stage):
            if revision.id not in held:
                held[revision.id] = _check(
                    inputs, revision, outcome, initial, checkpoints
                )
            if held[revision.id] is not Tri.TRUE:
                continue
            apply_effect(revision, effect, outcome, env)
            if revision.id not in outcome.applied:
                outcome.applied.append(revision.id)
        checkpoints[stage] = {line.offer.id: line.current for line in lines}
    return outcome


def _ordered(subset: tuple[RevisionRule, ...], stage: str) -> Iterable:
    """Yield (revision, effect) of one stage, in each revision's precedence."""
    for revision in subset:
        effects = [effect for effect in revision.effects if effect.stage == stage]
        for effect in _topological(effects, revision.ordering):
            yield revision, effect


def _topological(effects: list, edges: tuple[tuple[int, int], ...]) -> list:
    positions = {effect.position: effect for effect in effects}
    after: dict[int, set[int]] = {position: set() for position in positions}
    incoming = dict.fromkeys(positions, 0)
    for before, later in edges:
        if before in positions and later in positions:
            after[before].add(later)
            incoming[later] += 1
    ready = sorted(position for position, count in incoming.items() if count == 0)
    ordered = []
    while ready:
        position = ready.pop(0)
        ordered.append(positions[position])
        for later in sorted(after[position]):
            incoming[later] -= 1
            if incoming[later] == 0:
                ready.append(later)
        ready.sort()
    return ordered


def _check(
    inputs: Inputs,
    revision: RevisionRule,
    outcome: Outcome,
    initial: dict[int, Decimal],
    checkpoints: dict[str, dict[int, Decimal]],
) -> Tri:
    """Evaluate a revision's conditions on the amounts as they stand now."""

    def amounts(lines: list[LineState]) -> Amounts:
        ids = {line.offer.id for line in lines}

        def total(values: dict[int, Decimal] | None) -> Decimal:
            if values is None:
                return sum((line.current for line in lines), ZERO)
            return sum((value for key, value in values.items() if key in ids), ZERO)

        return Amounts(
            before_discounts=total(initial),
            after_item_discounts=total(checkpoints.get("catalog")),
            after_order_discounts=total(checkpoints.get("order")),
            shipping=outcome.shipping if outcome.shipping_known else None,
            quantity=sum(line.quantity for line in lines),
        )

    qualifying = [line for line in outcome.lines if qualifies(revision, line.offer)]
    data = ConditionInput(
        context=inputs.context,
        revision=revision,
        offers=tuple(line.offer for line in outcome.lines),
        qualifying=amounts(qualifying),
        order=amounts(outcome.lines),
    )
    result = evaluate_conditions(revision.conditions, data)
    subject = f"revision {revision.id}"
    if result.value is Tri.FALSE:
        outcome.decisions.append(
            Decision(subject, DecisionStatus.INELIGIBLE, "; ".join(result.reasons)),
        )
    elif result.value is Tri.UNKNOWN:
        outcome.decisions.append(
            Decision(subject, DecisionStatus.UNKNOWN, "; ".join(result.reasons)),
        )
        outcome.missing.extend(result.reasons)
    return result.value


def _shipping(inputs: Inputs, outcome: Outcome) -> None:
    """Take each group's cheapest quote that holds for the cart as it is now.

    A quote must be current, in the cart's currency and, when the carrier
    priced by order value, quoted for the cart's current value. Called before
    the stages and again at the shipping stage, after discounts changed it.
    """
    context = inputs.context
    groups = context.groups or ()
    keys = [group.key for group in groups] or ["all"]
    value = round_money(
        sum((line.current for line in outcome.lines), ZERO),
        context.minor_unit,
    )
    amounts = []
    for key in keys:
        quotes = [
            quote
            for quote in inputs.shipping
            if quote.group_key == key
            and quote.amount is not None
            and quote.currency == context.currency
            and (quote.observed_at is None or quote.observed_at <= context.now)
            and (quote.expires_at is None or quote.expires_at > context.now)
        ]
        holding = [
            quote
            for quote in quotes
            if quote.order_value is None or quote.order_value == value
        ]
        if not holding:
            outcome.missing.append(
                f"shipping quoted for an order of {quotes[0].order_value}, not {value}"
                if quotes
                else f"shipping quote for group {key}",
            )
            outcome.shipping, outcome.shipping_known = None, False
            return
        amounts.append(min(quote.amount for quote in holding))
    outcome.shipping, outcome.shipping_known = sum(amounts, ZERO), True


def unapplied_decisions(
    candidates: list[RevisionRule],
    best: Outcome,
    alone: dict[int, Outcome],
) -> list[Decision]:
    """Say why each candidate is not in the chosen combination."""
    decisions: list[Decision] = []
    for revision in candidates:
        if revision.id in best.applied:
            continue
        subject = f"revision {revision.id}"
        own = [
            d
            for d in alone.get(revision.id, Outcome(lines=[])).decisions
            if d.subject == subject
        ]
        decisions.extend(
            own
            or [Decision(subject, DecisionStatus.NOT_CHOSEN, "a better combination")],
        )
    return decisions


def total_money_rewards(outcome: Outcome) -> Decimal:
    """Known money rewards, to break ties between equal totals."""
    return sum(
        (
            reward.amount
            for reward in outcome.rewards
            if reward.credited_as == "money" and reward.amount is not None
        ),
        ZERO,
    )


def _uses_coupon(inputs: Inputs, outcome: Outcome) -> bool:
    """Tell whether an applied revision was activated by a code in the context."""
    codes = inputs.context.codes
    return any(
        code in codes
        for revision in inputs.revisions
        if revision.id in outcome.applied
        for _kind, code in revision.codes
        if code
    )


def _has_cashback(outcome: Outcome) -> bool:
    """Tell whether the combination earns a money reward of known amount."""
    return any(
        reward.credited_as == "money" and reward.amount is not None
        for reward in outcome.rewards
    )


def meets_benefits(inputs: Inputs, outcome: Outcome) -> bool:
    """Tell whether a combination uses exactly the benefits requested."""
    if inputs.benefits is None:
        return True
    used = {
        name
        for name, present in (
            ("coupon", _uses_coupon(inputs, outcome)),
            ("cashback", _has_cashback(outcome)),
        )
        if present
    }
    return used == inputs.benefits


def objective_amount(inputs: Inputs, outcome: Outcome) -> Decimal:
    """Use the same explicit comparison criterion as the projection selector."""
    merchandise = sum((line.current for line in outcome.lines), ZERO)
    if inputs.policy.objective == "items_payable":
        return merchandise
    fees, _missing = fee_total(inputs)
    if not outcome.shipping_known or outcome.shipping is None or fees is None:
        return Decimal("Infinity")
    total = merchandise + outcome.shipping + fees
    if inputs.policy.objective == "total_payable":
        return total
    if inputs.policy.objective == "estimated_net_cost":
        if not inputs.policy.net_cost_counts_money_rewards:
            return Decimal("Infinity")
        return total - total_money_rewards(outcome)
    msg = f"Unknown comparison objective: {inputs.policy.objective}"
    raise ValueError(msg)
