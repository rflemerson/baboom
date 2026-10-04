"""Apply one effect to the lines of a purchase.

Every immediate discount is limited to its eligible basis, allocated exactly
over the target lines, and recorded with what it was computed on. Rewards are
deferred and never reduce what is paid. A gift has no money value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from .money import ZERO, allocate, percent_of, round_money
from .types import (
    Adjustment,
    Decision,
    DecisionStatus,
    DeferredReward,
    Gift,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from .types import (
        CartLine,
        EffectRule,
        OfferFact,
        PurchaseContext,
        RevisionRule,
        RewardTermsFact,
        RouteFact,
        SelectedPrice,
    )

STAGES = ("catalog", "order", "payment", "shipping", "reward")


@dataclass
class LineState:
    """One line as effects change it."""

    offer: OfferFact
    price: SelectedPrice
    quantity: int
    initial: Decimal
    current: Decimal
    consumed: int = 0

    @classmethod
    def start(cls, line: CartLine, offer: OfferFact, price: SelectedPrice) -> LineState:
        """Begin a line at its base price."""
        subtotal = price.amount * line.quantity
        return cls(offer, price, line.quantity, subtotal, subtotal)

    def copy(self) -> LineState:
        """Return an independent copy for another combination."""
        return LineState(
            self.offer,
            self.price,
            self.quantity,
            self.initial,
            self.current,
            self.consumed,
        )

    @property
    def unit_current(self) -> Decimal:
        """The current price of one unit."""
        return self.current / self.quantity


class Outcome(Protocol):
    """What an effect writes to."""

    lines: list[LineState]
    adjustments: list
    rewards: list[DeferredReward]
    gifts: list
    decisions: list[Decision]
    assumptions: list[str]
    missing: list[str]
    shipping: Decimal | None
    shipping_known: bool
    schedule_rates: tuple[Decimal, ...]
    routes: dict[int, RouteFact]
    tracking_programs: dict[int, set[int]]


@dataclass(frozen=True)
class Environment:
    """What every effect of one evaluation shares."""

    context: PurchaseContext
    targets: Callable[[RevisionRule, OfferFact], bool]
    assume_full_caps: bool = False
    routes: tuple[RouteFact, ...] = ()


@dataclass
class _Step:
    """Everything one effect reads."""

    revision: RevisionRule
    effect: EffectRule
    outcome: Outcome
    env: Environment
    targets: list[LineState] = field(default_factory=list)

    @property
    def context(self) -> PurchaseContext:
        """The purchase context."""
        return self.env.context

    @property
    def minor(self) -> int:
        """The currency's precision."""
        return self.context.minor_unit

    @property
    def params(self) -> dict[str, object]:
        """The effect's parameters."""
        return self.effect.params

    def decimal(self, key: str) -> Decimal | None:
        """Read a decimal parameter."""
        value = self.params.get(key)
        return None if value is None else Decimal(str(value))


def apply_effect(
    revision: RevisionRule,
    effect: EffectRule,
    outcome: Outcome,
    env: Environment,
) -> None:
    """Apply one effect of one revision to the outcome."""
    step = _Step(revision, effect, outcome, env)
    step.targets = [line for line in outcome.lines if env.targets(revision, line.offer)]
    if effect.stage == "payment":
        step.targets = _without_included_payment_discount(step)
        if not step.targets:
            return
    HANDLERS[effect.kind](step)


def _without_included_payment_discount(step: _Step) -> list[LineState]:
    """Drop lines whose price already includes a payment discount.

    A line priced by Pix already carries its payment discount; a payment
    effect reaches only the other lines, and says which it left out.
    """
    included = [
        line
        for line in step.targets
        if "payment_discount" in line.price.already_included
    ]
    if included:
        step.outcome.decisions.append(
            Decision(
                f"revision {step.revision.id}",
                DecisionStatus.CONFLICT,
                "payment discount already in the price of offers "
                f"{sorted(line.offer.id for line in included)}; not applied to them",
            ),
        )
    return [line for line in step.targets if line not in included]


# Immediate discounts


def _basis(step: _Step) -> Decimal:
    """Return the amount an effect is computed on."""
    basis = step.effect.basis
    if basis == "initial":
        return sum((line.initial for line in step.targets), ZERO)
    if basis == "order_total":
        return sum((line.current for line in step.outcome.lines), ZERO)
    return sum((line.current for line in step.targets), ZERO)


def _discount(step: _Step, wanted: Decimal, basis: Decimal) -> None:
    """Take ``wanted`` off the target lines, within cap and eligible basis."""
    eligible = sum((line.current for line in step.targets), ZERO)
    amount = wanted
    if step.effect.cap is not None:
        amount = min(amount, step.effect.cap)
    amount = round_money(max(min(amount, eligible), ZERO), step.minor)
    if amount <= 0:
        return
    shares = allocate(amount, [line.current for line in step.targets], step.minor)
    for line, share in zip(step.targets, shares, strict=True):
        line.current -= share
    _record(step, basis, amount, shares)


def _record(
    step: _Step,
    basis: Decimal,
    amount: Decimal,
    shares: list[Decimal],
) -> None:
    step.outcome.adjustments.append(
        Adjustment(
            revision_id=step.revision.id,
            effect_position=step.effect.position,
            kind=step.effect.kind,
            stage=step.effect.stage,
            basis_amount=round_money(basis, step.minor),
            amount=amount,
            allocations=tuple(
                (line.offer.id, share)
                for line, share in zip(step.targets, shares, strict=True)
            ),
            order=len(step.outcome.adjustments) + 1,
        ),
    )


def _percentage(step: _Step) -> None:
    basis = _basis(step)
    rate = step.decimal("rate") or ZERO
    _discount(step, percent_of(basis, rate), basis)


def _fixed_amount(step: _Step) -> None:
    amount = step.decimal("amount") or ZERO
    allocation = step.effect.allocation
    if allocation not in {"per_unit", "per_line"}:
        _discount(step, amount, _basis(step))
        return
    remaining = step.effect.max_applications
    wanted = []
    for line in step.targets:
        count = line.quantity if allocation == "per_unit" else 1
        if remaining is not None:
            count = min(count, remaining)
            remaining -= count
        wanted.append(min(amount * count, line.current))
    total = sum(wanted, ZERO)
    if step.effect.cap is not None:
        total = min(total, step.effect.cap)
    total = round_money(total, step.minor)
    shares = allocate(total, wanted, step.minor)
    for line, share in zip(step.targets, shares, strict=True):
        line.current -= share
    if total:
        _record(step, _basis(step) + total, total, shares)


def _fixed_price(step: _Step) -> None:
    price = step.decimal("price") or ZERO
    wanted = sum(
        (max(line.unit_current - price, ZERO) * line.quantity for line in step.targets),
        ZERO,
    )
    _discount(step, wanted, _basis(step))


def _multibuy(step: _Step) -> None:
    """Buy ``buy`` pay ``pay``: the free units come off, once per full group."""
    buy = int(str(step.params["buy"]))
    pay = int(str(step.params["pay"]))
    units = [
        (line.unit_current, index)
        for index, line in enumerate(step.targets)
        for _ in range(line.quantity - line.consumed)
    ]
    groups = len(units) // buy
    if not step.params.get("repeat", True):
        groups = min(groups, 1)
    if step.effect.max_applications is not None:
        groups = min(groups, step.effect.max_applications)
    if groups == 0:
        step.outcome.decisions.append(
            Decision(
                f"revision {step.revision.id}",
                DecisionStatus.INELIGIBLE,
                f"fewer than {buy} units",
            ),
        )
        return
    cheapest_first = step.params.get("free_unit", "cheapest") == "cheapest"
    ordered = sorted(units, reverse=not cheapest_first)
    free = ordered[: groups * (buy - pay)]
    per_line = [ZERO] * len(step.targets)
    for unit_price, index in free:
        per_line[index] += unit_price
    if step.effect.consumes_units:
        used = [0] * len(step.targets)
        for _price, index in sorted(units)[: groups * buy]:
            used[index] += 1
        for line, count in zip(step.targets, used, strict=True):
            line.consumed += count
    basis = sum((line.current for line in step.targets), ZERO)
    amount = sum(per_line, ZERO)
    if step.effect.cap is not None:
        amount = min(amount, step.effect.cap)
    amount = round_money(amount, step.minor)
    shares = allocate(amount, per_line, step.minor)
    for line, share in zip(step.targets, shares, strict=True):
        line.current -= share
    _record(step, basis, amount, shares)


def _tiered(step: _Step) -> None:
    """Apply the highest tier the target quantity reaches, to every unit."""
    quantity = sum(line.quantity for line in step.targets)
    reached = [
        tier
        for tier in step.params.get("tiers", [])
        if isinstance(tier, dict) and int(str(tier["min_quantity"])) <= quantity
    ]
    if not reached:
        return
    tier = reached[-1]
    basis = sum((line.current for line in step.targets), ZERO)
    if tier.get("rate") is not None:
        wanted = percent_of(basis, Decimal(str(tier["rate"])))
    else:
        wanted = Decimal(str(tier["amount_off_per_unit"])) * quantity
    _discount(step, wanted, basis)


def _shipping_discount(step: _Step) -> None:
    """Discount shipping; with no shipping quote the effect cannot be computed."""
    outcome = step.outcome
    if not outcome.shipping_known or outcome.shipping is None:
        outcome.decisions.append(
            Decision(
                f"revision {step.revision.id}",
                DecisionStatus.UNKNOWN,
                "shipping not quoted",
            ),
        )
        outcome.missing.append("shipping quote")
        return
    shipping = outcome.shipping
    if step.params.get("free"):
        amount = shipping
    elif step.params.get("rate") is not None:
        amount = percent_of(shipping, Decimal(str(step.params["rate"])))
    else:
        amount = step.decimal("amount") or ZERO
    if step.effect.cap is not None:
        amount = min(amount, step.effect.cap)
    amount = round_money(min(amount, shipping), step.minor)
    outcome.shipping = shipping - amount
    outcome.adjustments.append(
        Adjustment(
            revision_id=step.revision.id,
            effect_position=step.effect.position,
            kind=step.effect.kind,
            stage=step.effect.stage,
            basis_amount=shipping,
            amount=amount,
            order=len(outcome.adjustments) + 1,
        ),
    )


def _subscription(step: _Step) -> None:
    """Price a known horizon of deliveries; only when a subscription is chosen."""
    if step.context.subscription is not True:
        step.outcome.decisions.append(
            Decision(
                f"revision {step.revision.id}",
                DecisionStatus.UNKNOWN
                if step.context.subscription is None
                else DecisionStatus.INELIGIBLE,
                "subscription not chosen",
            ),
        )
        return
    deliveries = int(str(step.params.get("minimum_deliveries", 1)))
    first_rate = step.decimal("first_delivery_rate")
    recurring_rate = step.decimal("recurring_rate")
    base = sum((line.current for line in step.targets), ZERO)
    applied_before = len(step.outcome.adjustments)
    _discount(step, percent_of(base, first_rate) if first_rate else ZERO, base)
    first_discount = sum(
        (a.amount for a in step.outcome.adjustments[applied_before:]),
        ZERO,
    )
    recurring_discount = percent_of(base, recurring_rate) if recurring_rate else ZERO
    if step.effect.cap is not None:
        recurring_discount = min(recurring_discount, step.effect.cap)
    recurring = round_money(base - recurring_discount, step.minor)
    # The first delivery is what the cart charges; later ones the same
    # basis less their own (capped) discount.
    step.outcome.schedule_rates = (
        base - first_discount,
        *([recurring] * (deliveries - 1)),
    )
    step.outcome.assumptions.append(
        f"subscription of {deliveries} deliveries every "
        f"{step.params.get('interval_days')} days at today's price",
    )


def _gift(step: _Step) -> None:
    """Record a gift; it is never money."""
    step.outcome.gifts.append(
        Gift(
            revision_id=step.revision.id,
            description=str(step.params.get("description") or ""),
            quantity=int(str(step.params.get("quantity", 1))),
            listing_variant_id=(
                int(str(step.params["listing_variant_id"]))
                if step.params.get("listing_variant_id") is not None
                else None
            ),
        ),
    )


# Deferred rewards


def _reward_basis(step: _Step) -> Decimal | None:
    terms = step.effect.reward
    if terms is None:
        return None
    if terms.eligible_basis == "items_before_discounts":
        basis = sum((line.initial for line in step.targets), ZERO)
    elif terms.eligible_basis == "order_total":
        basis = sum((line.current for line in step.outcome.lines), ZERO)
    else:
        basis = sum((line.current for line in step.targets), ZERO)
    if terms.includes_shipping:
        if not step.outcome.shipping_known or step.outcome.shipping is None:
            return None
        basis += step.outcome.shipping
    return basis


def _cashback(step: _Step) -> None:
    """Estimate cashback on its own basis; it never reduces what is paid."""
    terms = step.effect.reward
    basis = _reward_basis(step)
    subject = f"revision {step.revision.id}"
    if terms is None or terms.rate is None:
        step.outcome.decisions.append(
            Decision(subject, DecisionStatus.UNKNOWN, "cashback rate unknown"),
        )
        return
    if terms.tracking_required and not _tracked(step, terms):
        return
    if basis is None:
        step.outcome.decisions.append(
            Decision(subject, DecisionStatus.UNKNOWN, "cashback basis needs shipping"),
        )
        return
    if terms.minimum is not None and basis < terms.minimum:
        step.outcome.decisions.append(
            Decision(subject, DecisionStatus.INELIGIBLE, "below the cashback minimum"),
        )
        return
    amount: Decimal | None = percent_of(basis, terms.rate)
    assumptions: list[str] = []
    if terms.cap is not None and amount is not None:
        amount = min(amount, terms.cap)
        if terms.cap_period not in ("", "transaction"):
            # What the buyer already used of a monthly or campaign cap is not
            # known: the estimate holds only if the whole cap is assumed.
            if step.env.assume_full_caps:
                assumptions.append(
                    f"the whole {terms.cap_period} cap of {terms.cap} is available",
                )
            else:
                amount = None
    step.outcome.rewards.append(
        DeferredReward(
            revision_id=step.revision.id,
            credited_as=terms.credited_as,
            amount=None if amount is None else round_money(amount, step.minor),
            unit=step.revision.currency,
            basis_amount=round_money(basis, step.minor),
            assumptions=tuple(assumptions),
        ),
    )
    if amount is None:
        step.outcome.decisions.append(
            Decision(subject, DecisionStatus.UNKNOWN, "remaining cap unknown"),
        )
    step.outcome.assumptions.extend(assumptions)


def _tracked(step: _Step, terms: RewardTermsFact) -> bool:
    """Find, for every target line, a route that keeps the programme's tracking.

    Cashback a programme credits only through its own activation link is not
    a reward of the purchase unless the buyer is sent through that link.
    Without such a route for every line, the reward is unknown.
    """
    chosen: dict[int, RouteFact] = {}
    for line in step.targets:
        required = set(step.outcome.tracking_programs.get(line.offer.id, set()))
        if terms.program_id is not None:
            required.add(terms.program_id)
        route = next(
            (
                route
                for route in sorted(step.env.routes, key=lambda item: item.id)
                if terms.program_id is not None
                and route.offer_id == line.offer.id
                and route.kind == "cashback_activation"
                and required
                <= (
                    route.compatible_programs
                    | (
                        frozenset({route.program_id})
                        if route.program_id is not None
                        else frozenset()
                    )
                )
            ),
            None,
        )
        if route is None:
            step.outcome.decisions.append(
                Decision(
                    f"revision {step.revision.id}",
                    DecisionStatus.UNKNOWN,
                    f"cashback needs tracking; no activation route for offer "
                    f"{line.offer.id}",
                ),
            )
            return False
        chosen[line.offer.id] = route
    step.outcome.routes.update(chosen)
    if terms.program_id is not None:
        for offer_id in chosen:
            step.outcome.tracking_programs.setdefault(offer_id, set()).add(
                terms.program_id
            )
    return True


def _points(step: _Step) -> None:
    """Points are a unit of their own, never money."""
    terms = step.effect.reward
    per_unit = step.decimal("per_currency_unit")
    basis = sum((line.current for line in step.targets), ZERO)
    points = per_unit * basis if per_unit is not None else step.decimal("points")
    step.outcome.rewards.append(
        DeferredReward(
            revision_id=step.revision.id,
            credited_as="points",
            amount=None if points is None else points.to_integral_value(),
            unit=str(terms.program_id) if terms and terms.program_id else "points",
            basis_amount=round_money(basis, step.minor),
        ),
    )


HANDLERS: dict[str, Callable[[_Step], None]] = {
    "percentage": _percentage,
    "fixed_amount": _fixed_amount,
    "fixed_price": _fixed_price,
    "multibuy": _multibuy,
    "tiered": _tiered,
    "shipping_discount": _shipping_discount,
    "subscription": _subscription,
    "gift": _gift,
    "cashback": _cashback,
    "points": _points,
}
