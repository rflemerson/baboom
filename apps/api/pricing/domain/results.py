"""Assemble a pricing result: totals, payment schedule, routes and validity."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from promotions.rules.conditions import leaves

from .money import ZERO, allocate, round_money
from .types import (
    ENGINE_VERSION,
    Decision,
    OptimizationStatus,
    PricingResult,
    ScheduledPayment,
    SelectedPrice,
)

if TYPE_CHECKING:
    from .application import Outcome
    from .types import PaymentChoice, RevisionRule
from .candidates import static_refusal
from .charges import fee_total
from .inputs import Inputs, fingerprint
from .routes import chosen_routes


def build_result(
    inputs: Inputs,
    selected: list[SelectedPrice],
    payment: PaymentChoice | None,
    outcome: Outcome,
    status: OptimizationStatus,
) -> PricingResult:
    """Assemble the result of the chosen combination."""
    decisions, missing, assumptions = (
        outcome.decisions,
        outcome.missing,
        outcome.assumptions,
    )
    context, policy = inputs.context, inputs.policy
    minor = context.minor_unit
    merchandise = round_money(
        sum((line.current for line in outcome.lines), ZERO), minor
    )
    shipping = round_money(outcome.shipping, minor) if outcome.shipping_known else None
    fees, fee_missing = fee_total(inputs)
    missing = [*missing, *fee_missing]
    total = (
        merchandise + shipping + fees
        if shipping is not None and fees is not None
        else None
    )
    schedule = _schedule(
        inputs, outcome, payment, total if total is not None else merchandise
    )
    due_now = schedule[0].amount if schedule and total is not None else None
    money_rewards = [
        reward.amount
        for reward in outcome.rewards
        if reward.credited_as == "money" and reward.amount is not None
    ]
    net = (
        total - sum(money_rewards, ZERO)
        if total is not None and policy.net_cost_counts_money_rewards
        else None
    )
    routes, limitations = chosen_routes(inputs, outcome)
    return PricingResult(
        scenario=policy.scenario,
        currency=context.currency,
        lines=context.lines,
        selected_prices=tuple(selected),
        payment=payment,
        merchandise_total=merchandise,
        shipping_total=shipping,
        tax_fee_total=fees,
        total_payable=total,
        due_now=due_now,
        payment_schedule=tuple(schedule),
        adjustments=tuple(outcome.adjustments),
        deferred_rewards=tuple(outcome.rewards),
        gifts=tuple(outcome.gifts),
        estimated_net_cost=net,
        decisions=tuple(_unique(decisions)),
        assumptions=tuple(dict.fromkeys(assumptions)),
        missing_context=tuple(dict.fromkeys(missing)),
        applied_revisions=tuple(outcome.applied),
        purchase_routes=routes,
        route_limitations=limitations,
        input_fingerprint=fingerprint(inputs),
        engine_version=ENGINE_VERSION,
        policy_key=policy.key,
        policy_version=policy.version,
        evaluated_at=context.now,
        expires_at=_expiry(inputs, selected, outcome),
        optimization_status=status,
    )


def _schedule(
    inputs: Inputs,
    outcome: Outcome,
    payment: PaymentChoice | None,
    total: Decimal,
) -> list[ScheduledPayment]:
    """Split the total into the chosen installments, or one payment."""
    minor = inputs.context.minor_unit
    if outcome.schedule_rates:
        return [
            ScheduledPayment(
                index + 1, round_money(amount, minor), f"delivery {index + 1}"
            )
            for index, amount in enumerate(outcome.schedule_rates)
        ]
    count = payment.installments if payment is not None else 1
    if count <= 1:
        return [ScheduledPayment(1, total, "at purchase")]
    shares = allocate(total, [Decimal(1)] * count, minor)
    return [
        ScheduledPayment(index + 1, share, f"installment {index + 1}")
        for index, share in enumerate(shares)
    ]


def _expiry(
    inputs: Inputs,
    selected: list[SelectedPrice],
    outcome: Outcome,
) -> datetime | None:
    """Return when this alternative stops holding: only what it used counts."""
    context = inputs.context
    chosen = {price.observation_id for price in selected}
    moments = [
        price.fresh_until
        for price in inputs.prices
        if price.id in chosen and price.fresh_until is not None
    ]
    moments += outcome.quote_expiries
    if inputs.fees_status in {"included_in_prices", "consulted"}:
        moments += [fee.expires_at for fee in inputs.fees if fee.expires_at is not None]
    for revision in inputs.revisions:
        if revision.id in outcome.applied:
            if revision.ends_at is not None:
                moments.append(revision.ends_at)
        elif (
            not inputs.policy.apply_benefits
            or (revision.ends_at is not None and revision.ends_at <= context.now)
            or static_refusal(revision, inputs, outcome.lines) is not None
        ):
            continue
        elif revision.starts_at is not None and revision.starts_at > context.now:
            moments.append(revision.starts_at)
        moments += _calendar_boundaries(revision, context.now)
    return min(moments) if moments else None


def _calendar_boundaries(revision: RevisionRule, now: datetime) -> list[datetime]:
    """Return the next moments a revision's calendar conditions change."""
    boundaries: list[datetime] = []
    for leaf in leaves(revision.conditions.get("root")):
        if leaf.get("kind") != "calendar":
            continue
        local = now.astimezone(ZoneInfo(revision.timezone))
        for offset in (0, 1):
            day = local.date() + timedelta(days=offset)
            for boundary in ("00:00", leaf.get("start_time"), leaf.get("end_time")):
                if boundary:
                    moment = datetime.combine(
                        day, time.fromisoformat(str(boundary)), local.tzinfo
                    )
                    if moment > now:
                        boundaries.append(moment)
    return boundaries


def _unique(decisions: list[Decision]) -> list[Decision]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Decision] = []
    for decision in decisions:
        key = (decision.subject, decision.status, decision.reason)
        if key not in seen:
            seen.add(key)
            unique.append(decision)
    return unique


def empty_result(
    inputs: Inputs,
    decisions: list[Decision],
    missing: list[str],
    assumptions: list[str],
    status: OptimizationStatus,
) -> PricingResult:
    """Return a result with no price: every total unknown, every reason kept.

    ``status`` is ``complete`` only when no eligible alternative exists;
    ``bounded`` when the search stopped before covering every alternative.
    """
    context, policy = inputs.context, inputs.policy
    return PricingResult(
        scenario=policy.scenario,
        currency=context.currency,
        lines=context.lines,
        selected_prices=(),
        payment=None,
        merchandise_total=None,
        shipping_total=None,
        tax_fee_total=None,
        total_payable=None,
        due_now=None,
        payment_schedule=(),
        adjustments=(),
        deferred_rewards=(),
        gifts=(),
        estimated_net_cost=None,
        decisions=tuple(_unique(decisions)),
        assumptions=tuple(assumptions),
        missing_context=tuple(dict.fromkeys(missing)),
        applied_revisions=(),
        purchase_routes=(),
        route_limitations=(),
        input_fingerprint=fingerprint(inputs),
        engine_version=ENGINE_VERSION,
        policy_key=policy.key,
        policy_version=policy.version,
        evaluated_at=context.now,
        expires_at=None,
        optimization_status=status,
    )
