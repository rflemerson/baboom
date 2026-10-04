"""Evaluate one purchase scenario: base prices, promotions, shipping, rewards.

``evaluate`` is a pure function. It selects a base price per line for the
policy's scenario, keeps the revisions that apply, builds the combinations
compatibility allows, applies each combination's effects stage by stage, and
returns the cheapest total payable with every decision explained.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from promotions.rules.conditions import leaves
from promotions.rules.effects import REWARD_EFFECTS

from .base_prices import select_prices
from .conditions import Amounts, ConditionInput
from .conditions import evaluate as evaluate_conditions
from .effects import (
    STAGES,
    SUPPORTED_EFFECTS,
    Environment,
    LineState,
    apply_effect,
    unsupported_settings,
)
from .money import ZERO, allocate, round_money
from .scopes import qualifies, targets
from .types import (
    ENGINE_VERSION,
    CartLine,
    ChosenRoute,
    Decision,
    DecisionStatus,
    DeferredReward,
    OptimizationStatus,
    PricingResult,
    ScheduledPayment,
    SelectedPrice,
    Tri,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .types import (
        CompatibilityFact,
        FeeFact,
        OfferFact,
        Policy,
        PriceFact,
        PurchaseContext,
        RevisionRule,
        RouteFact,
        ShippingFact,
    )

CLAIM_LEAVES = frozenset({"new_customer", "program_member", "subscription"})
REWARD_KINDS = REWARD_EFFECTS


@dataclass(frozen=True)
class Inputs:
    """Everything one evaluation reads."""

    context: PurchaseContext
    offers: tuple[OfferFact, ...]
    prices: tuple[PriceFact, ...]
    revisions: tuple[RevisionRule, ...]
    policy: Policy
    shipping: tuple[ShippingFact, ...] = ()
    fees: tuple[FeeFact, ...] = ()
    routes: tuple[RouteFact, ...] = ()
    # "included_in_prices": the market's prices carry every tax, so only fees
    # quoted on top are added; "consulted": a source answered for every
    # charge, so ``fees`` is complete (possibly empty); "partial": some
    # charges were read, not all; "not_consulted": nobody asked;
    # "inclusion_unknown": not even whether prices include taxes is known.
    # Only the first two give a known total.
    fees_status: str = "not_consulted"
    # Benefits the chosen combination must use: "coupon", "cashback". Empty
    # asks for the best combination whatever it uses.
    requirement: frozenset[str] = frozenset()


@dataclass
class _Outcome:
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


def evaluate(inputs: Inputs) -> PricingResult:
    """Return the scenario's result for these inputs and this ``now``."""
    context, policy = inputs.context, inputs.policy
    decisions: list[Decision] = []
    missing: list[str] = []
    assumptions: list[str] = []
    offers = {offer.id: offer for offer in inputs.offers}

    selected = select_prices(inputs, offers, decisions, missing)
    if selected is None:
        return _empty(inputs, decisions, missing, assumptions)

    lines = [
        LineState.start(line, offers[line.offer_id], price)
        for line, price in zip(context.lines, selected, strict=True)
    ]
    candidates = _candidates(inputs, lines, decisions)
    subsets, status = _combinations(candidates, policy, decisions, assumptions)

    best: _Outcome | None = None
    best_key: tuple[Decimal, Decimal, int] | None = None
    alone: dict[int, _Outcome] = {}
    for subset in subsets:
        outcome = _apply(inputs, lines, subset)
        if len(subset) == 1:
            alone[subset[0].id] = outcome
        if not _meets(inputs, outcome):
            continue
        key = (
            _objective_amount(inputs, outcome),
            -_money_rewards(outcome),
            -len(outcome.applied),
        )
        if best_key is None or key < best_key:
            best, best_key = outcome, key
    if best is None:
        decisions.append(
            Decision(
                "scenario",
                DecisionStatus.INELIGIBLE,
                f"no combination uses {sorted(inputs.requirement)}",
            ),
        )
        return _empty(inputs, decisions, missing, assumptions)
    decisions += _unapplied(candidates, best, alone)
    best.decisions[:0] = decisions
    best.missing[:0] = missing
    best.assumptions[:0] = assumptions
    return _result(inputs, selected, best, status)


# Base prices


# Candidate revisions


def _candidates(
    inputs: Inputs,
    lines: list[LineState],
    decisions: list[Decision],
) -> list[RevisionRule]:
    """Keep the revisions that may apply to these lines in this scenario."""
    context, policy = inputs.context, inputs.policy
    kept: list[RevisionRule] = []
    for revision in sorted(inputs.revisions, key=lambda item: item.id):
        subject = f"revision {revision.id}"
        reason = _static_refusal(revision, inputs, lines)
        if reason is not None:
            status, text = reason
            decisions.append(Decision(subject, status, text))
            continue
        if revision.starts_at and context.now < revision.starts_at:
            decisions.append(
                Decision(subject, DecisionStatus.INELIGIBLE, "not started")
            )
            continue
        if revision.ends_at and context.now >= revision.ends_at:
            decisions.append(Decision(subject, DecisionStatus.INELIGIBLE, "ended"))
            continue
        effective = revision
        if not policy.allow_rewards:
            effective = replace(
                revision,
                effects=tuple(
                    e for e in revision.effects if e.kind not in REWARD_KINDS
                ),
            )
            if not effective.effects:
                decisions.append(
                    Decision(
                        subject, DecisionStatus.INELIGIBLE, "scenario excludes rewards"
                    ),
                )
                continue
        kept.append(effective)
    return kept


def _static_refusal(
    revision: RevisionRule,
    inputs: Inputs,
    lines: list[LineState],
) -> tuple[DecisionStatus, str] | None:
    """Return why a revision cannot apply before any arithmetic, or None."""
    checks = (
        _status_refusal(revision, inputs),
        _terms_refusal(revision, inputs.policy),
        _reach_refusal(revision, lines, len(inputs.context.groups)),
    )
    return next((refusal for refusal in checks if refusal is not None), None)


def _status_refusal(
    revision: RevisionRule,
    inputs: Inputs,
) -> tuple[DecisionStatus, str] | None:
    """Refuse a revision not executable, or in another currency."""
    if revision.status == "informative":
        return DecisionStatus.INFORMATIVE, "terms not sufficient to compute"
    if revision.status != "executable":
        return DecisionStatus.INELIGIBLE, f"revision is {revision.status}"
    if revision.currency != inputs.context.currency:
        return DecisionStatus.UNSUPPORTED, "terms in another currency"
    unsupported = [e.kind for e in revision.effects if e.kind not in SUPPORTED_EFFECTS]
    if unsupported:
        return DecisionStatus.UNSUPPORTED, f"effects {unsupported} not computed"
    limits = [problem for e in revision.effects for problem in unsupported_settings(e)]
    if limits:
        return DecisionStatus.UNSUPPORTED, "; ".join(limits)
    return None


def _terms_refusal(
    revision: RevisionRule,
    policy: Policy,
) -> tuple[DecisionStatus, str] | None:
    """Refuse terms the scenario does not count: codes or excluded conditions."""
    code_kinds = {kind for kind, _code in revision.codes}
    if code_kinds & {"public_code", "personal_code"} and not policy.allow_codes:
        return DecisionStatus.INELIGIBLE, "scenario excludes codes"
    if "personal_code" in code_kinds and not policy.allow_private_codes:
        return DecisionStatus.INELIGIBLE, "personal code"
    excluded = sorted(
        kind
        for kind in _leaf_kinds(revision.conditions.get("root"))
        if kind not in policy.allow_conditions and kind != "code_required"
    )
    if excluded:
        return DecisionStatus.INELIGIBLE, f"scenario excludes {excluded}"
    return None


GROUP_TARGETS = frozenset({"order", "group"})
GROUP_SCOPES = frozenset({"checkout_group", "seller"})


def _per_group(revision: RevisionRule) -> bool:
    """Tell whether a revision's terms depend on how lines are grouped."""
    if any(
        effect.target in GROUP_TARGETS or effect.basis == "order_total"
        for effect in revision.effects
    ):
        return True
    root = revision.conditions.get("root")
    return any(
        isinstance(leaf, dict) and leaf.get("scope") in GROUP_SCOPES
        for leaf in _leaves(root)
    )


def _leaves(node: object) -> list[dict]:
    return list(leaves(node))


def _reach_refusal(
    revision: RevisionRule,
    lines: list[LineState],
    groups: int = 1,
) -> tuple[DecisionStatus, str] | None:
    """Refuse a revision that reaches no line, or repeats an included discount.

    With several checkout groups, terms that depend on the order or group
    are not evaluated per group yet: they are unsupported, never applied to
    the whole cart as if it were one order.
    """
    if groups > 1 and _per_group(revision):
        return (
            DecisionStatus.UNSUPPORTED,
            "order-level terms across several checkout groups",
        )
    if not any(targets(revision, line.offer) for line in lines):
        return DecisionStatus.INELIGIBLE, "targets none of these offers"
    if _payment_already_included(revision, lines):
        return DecisionStatus.CONFLICT, "payment discount already in the price"
    return None


def _leaf_kinds(node: object) -> set[str]:
    return {str(leaf.get("kind")) for leaf in leaves(node)}


def _payment_already_included(revision: RevisionRule, lines: list[LineState]) -> bool:
    """Tell whether a payment discount would repeat one already in the price."""
    payment_effects = [e for e in revision.effects if e.stage == "payment"]
    if not payment_effects:
        return False
    targeted = [line for line in lines if targets(revision, line.offer)]
    return bool(targeted) and all(
        "payment_discount" in line.price.already_included for line in targeted
    )


# Combinations


def _names(rule: CompatibilityFact, other: RevisionRule) -> bool:
    """Tell whether a compatibility rule is about another revision."""
    if rule.other_kind == "promotion":
        return rule.other_ref == str(other.promotion_id)
    if rule.other_kind == "effect_kind":
        return rule.other_ref in {effect.kind for effect in other.effects}
    return False


def _compatible(first: RevisionRule, second: RevisionRule) -> tuple[bool, str]:
    """Whether two revisions combine, and who decides when they do not."""
    verdicts = [
        (rule.verdict, rule.chooser)
        for own, other in ((first, second), (second, first))
        for rule in own.compatibility
        if _names(rule, other)
    ]
    if any(verdict == "forbidden" for verdict, _ in verdicts):
        chooser = next(c for v, c in verdicts if v == "forbidden")
        return False, chooser
    if any(verdict == "allowed" for verdict, _ in verdicts):
        return True, ""
    return False, "buyer_choice"


def _combinations(
    candidates: list[RevisionRule],
    policy: Policy,
    decisions: list[Decision],
    assumptions: list[str],
) -> tuple[list[tuple[RevisionRule, ...]], OptimizationStatus]:
    """Return the pairwise-compatible subsets, within a budget of visited nodes.

    The search grows a subset only with candidates compatible with every
    member, so incompatible promotions cost one node each instead of an
    exponential enumeration. ``max_combinations`` bounds the nodes visited;
    when the search stops early the result says ``bounded``.
    """
    store_pairs: list[tuple[int, int]] = []
    neighbours: dict[int, set[int]] = {index: set() for index in range(len(candidates))}
    for i, j in itertools.combinations(range(len(candidates)), 2):
        ok, chooser = _compatible(candidates[i], candidates[j])
        if ok:
            neighbours[i].add(j)
        elif chooser == "store_imposed":
            store_pairs.append((candidates[i].id, candidates[j].id))
    for first_id, second_id in store_pairs:
        decisions.append(
            Decision(
                f"revisions {first_id} and {second_id}",
                DecisionStatus.CONFLICT,
                "the store chooses one",
            ),
        )
    dropped = _store_choice(store_pairs, assumptions)
    allowed = {i for i, c in enumerate(candidates) if c.id not in dropped}
    search = _Search(candidates, neighbours, policy.max_combinations)
    search.grow((), allowed)
    status = (
        OptimizationStatus.BOUNDED if search.stopped else OptimizationStatus.COMPLETE
    )
    return search.subsets, status


@dataclass
class _Search:
    """A depth-first search over compatible subsets, with a node budget."""

    candidates: list[RevisionRule]
    neighbours: dict[int, set[int]]
    budget: int
    subsets: list[tuple[RevisionRule, ...]] = field(default_factory=lambda: [()])
    visited: int = 1
    stopped: bool = False

    def grow(self, members: tuple[int, ...], options: set[int]) -> None:
        """Extend a subset with each option compatible with all its members."""
        for index in sorted(options):
            if members and index < members[-1]:
                continue
            if self.visited >= self.budget:
                self.stopped = True
                return
            self.visited += 1
            subset = (*members, index)
            self.subsets.append(tuple(self.candidates[i] for i in subset))
            self.grow(subset, options & self.neighbours[index])
            if self.stopped:
                return


def _store_choice(
    store_pairs: list[tuple[int, int]],
    assumptions: list[str],
) -> set[int]:
    """Return the revisions dropped where the store picks between two.

    The store's choice is not known; the revision published first is assumed,
    and the assumption is reported.
    """
    assumptions.extend(
        f"the store's choice between revisions {a} and {b} assumed to be {min(a, b)}"
        for a, b in store_pairs
    )
    return {max(pair) for pair in store_pairs}


# Application


def _apply(
    inputs: Inputs,
    start: list[LineState],
    subset: tuple[RevisionRule, ...],
) -> _Outcome:
    """Apply one combination stage by stage; conditions are read as they stand."""
    context = inputs.context
    lines = [line.copy() for line in start]
    outcome = _Outcome(lines=lines)
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
            _match_order_value(inputs, outcome)
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
    outcome: _Outcome,
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


def _match_order_value(inputs: Inputs, outcome: _Outcome) -> None:
    """Drop shipping quoted for another order value than the cart now has.

    A carrier that prices by order value quoted one cart; after discounts
    the cart may be worth another amount, and that quote no longer holds.
    """
    if not outcome.shipping_known:
        return
    value = round_money(
        sum((line.current for line in outcome.lines), ZERO),
        inputs.context.minor_unit,
    )
    for quote in inputs.shipping:
        if quote.order_value is not None and quote.order_value != value:
            outcome.missing.append(
                f"shipping quoted for an order of {quote.order_value}, not {value}",
            )
            outcome.shipping, outcome.shipping_known = None, False
            return


def _shipping(inputs: Inputs, outcome: _Outcome) -> None:
    """Read the known shipping of every checkout group, or mark it unknown."""
    groups = inputs.context.groups or ()
    keys = [group.key for group in groups] or ["all"]
    quotes = {
        quote.group_key: quote
        for quote in inputs.shipping
        if quote.currency == inputs.context.currency
        and (quote.observed_at is None or quote.observed_at <= inputs.context.now)
        and (quote.expires_at is None or quote.expires_at > inputs.context.now)
    }
    amounts = []
    for key in keys:
        quote = quotes.get(key)
        if (
            quote is None
            or quote.amount is None
            or quote.currency != inputs.context.currency
        ):
            outcome.missing.append(f"shipping quote for group {key}")
            outcome.shipping, outcome.shipping_known = None, False
            return
        amounts.append(quote.amount)
    outcome.shipping, outcome.shipping_known = sum(amounts, ZERO), True


def _unapplied(
    candidates: list[RevisionRule],
    best: _Outcome,
    alone: dict[int, _Outcome],
) -> list[Decision]:
    """Say why each candidate is not in the chosen combination."""
    decisions: list[Decision] = []
    for revision in candidates:
        if revision.id in best.applied:
            continue
        subject = f"revision {revision.id}"
        own = [
            d
            for d in alone.get(revision.id, _Outcome(lines=[])).decisions
            if d.subject == subject
        ]
        decisions.extend(
            own
            or [Decision(subject, DecisionStatus.NOT_CHOSEN, "a better combination")],
        )
    return decisions


def _money_rewards(outcome: _Outcome) -> Decimal:
    """Known money rewards, to break ties between equal totals."""
    return sum(
        (
            reward.amount
            for reward in outcome.rewards
            if reward.credited_as == "money" and reward.amount is not None
        ),
        ZERO,
    )


def _uses_coupon(inputs: Inputs, outcome: _Outcome) -> bool:
    """Tell whether an applied revision was activated by a code in the context."""
    codes = inputs.context.codes
    return any(
        code in codes
        for revision in inputs.revisions
        if revision.id in outcome.applied
        for _kind, code in revision.codes
        if code
    )


def _has_cashback(outcome: _Outcome) -> bool:
    """Tell whether the combination earns a money reward of known amount."""
    return any(
        reward.credited_as == "money" and reward.amount is not None
        for reward in outcome.rewards
    )


def _meets(inputs: Inputs, outcome: _Outcome) -> bool:
    """Tell whether a combination uses every benefit the request requires."""
    checks = {
        "coupon": lambda: _uses_coupon(inputs, outcome),
        "cashback": lambda: _has_cashback(outcome),
    }
    return all(checks[name]() for name in inputs.requirement)


def _objective_amount(inputs: Inputs, outcome: _Outcome) -> Decimal:
    """Use the same explicit comparison criterion as the projection selector."""
    merchandise = sum((line.current for line in outcome.lines), ZERO)
    if inputs.policy.objective == "items_payable":
        return merchandise
    fees, _missing = _fees(inputs)
    if not outcome.shipping_known or outcome.shipping is None or fees is None:
        return Decimal("Infinity")
    total = merchandise + outcome.shipping + fees
    if inputs.policy.objective == "total_payable":
        return total
    if inputs.policy.objective == "estimated_net_cost":
        if not inputs.policy.net_cost_counts_money_rewards:
            return Decimal("Infinity")
        return total - _money_rewards(outcome)
    msg = f"Unknown comparison objective: {inputs.policy.objective}"
    raise ValueError(msg)


# Result


def _result(
    inputs: Inputs,
    selected: list[SelectedPrice],
    outcome: _Outcome,
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
    fees, fee_missing = _fees(inputs)
    missing = [*missing, *fee_missing]
    total = (
        merchandise + shipping + fees
        if shipping is not None and fees is not None
        else None
    )
    schedule = _schedule(inputs, outcome, total if total is not None else merchandise)
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
    routes, limitations = _routes(inputs, outcome)
    return PricingResult(
        scenario=policy.scenario,
        currency=context.currency,
        lines=context.lines,
        selected_prices=tuple(selected),
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
        expires_at=_expiry(inputs, outcome),
        optimization_status=status,
    )


ROUTE_PREFERENCE = ("direct", "affiliate", "marketplace_listing")


def _routes(
    inputs: Inputs,
    outcome: _Outcome,
) -> tuple[tuple[ChosenRoute, ...], tuple[str, ...]]:
    """Choose how to buy each line, and say where a link may not hold.

    A route a reward required wins; otherwise the curated direct, affiliate
    or listing route, preferring one that opens the exact variant. A line
    with none keeps the offer's own link. A third-party seller's offer whose
    link does not fix the seller is reported: the page may sell another's.
    """
    offers = {offer.id: offer for offer in inputs.offers}
    chosen: list[ChosenRoute] = []
    limitations: list[str] = []
    for line in inputs.context.lines:
        route = outcome.routes.get(line.offer_id) or _curated_route(
            inputs, line.offer_id
        )
        offer = offers.get(line.offer_id)
        fixes_seller = bool(route and route.fixes_seller) or bool(
            offer and offer.seller_is_owner,
        )
        reason = (
            "required by a reward"
            if line.offer_id in outcome.routes
            else ("curated route" if route else "the offer's own link")
        )
        chosen.append(
            ChosenRoute(
                offer_id=line.offer_id,
                route_id=route.id if route else None,
                url=route.url if route else None,
                fixes_seller=fixes_seller,
                reason=reason,
                fixes_variant=bool(route and route.fixes_variant),
                instructions=route.instructions if route else "",
            ),
        )
        if not fixes_seller:
            limitations.append(
                f"the link to offer {line.offer_id} may open another seller",
            )
    return tuple(chosen), tuple(limitations)


def _curated_route(inputs: Inputs, offer_id: int) -> RouteFact | None:
    candidates = [
        route
        for route in inputs.routes
        if route.offer_id == offer_id and route.kind in ROUTE_PREFERENCE
    ]
    candidates.sort(
        key=lambda route: (
            not route.fixes_variant,
            ROUTE_PREFERENCE.index(route.kind),
            route.id,
        ),
    )
    return candidates[0] if candidates else None


def _fees(inputs: Inputs) -> tuple[Decimal | None, list[str]]:
    """Sum fees not already in prices; an unknown fee leaves the sum unknown.

    No fee is zero only when the market's prices include taxes or a source
    was consulted; otherwise taxes and fees are unknown.
    """
    unknown = {
        "not_consulted": "taxes and fees not consulted",
        "partial": "taxes and fees consultation partial",
        "inclusion_unknown": "whether prices include taxes is unknown",
    }
    if inputs.fees_status in unknown:
        return None, [unknown[inputs.fees_status]]
    total = ZERO
    missing: list[str] = []
    for fee in inputs.fees:
        if fee.included_in_price:
            continue
        if fee.amount is None or fee.currency != inputs.context.currency:
            missing.append(f"{fee.kind} for group {fee.group_key}")
            continue
        total += fee.amount
    return (
        (None, missing)
        if missing
        else (round_money(total, inputs.context.minor_unit), [])
    )


def _schedule(
    inputs: Inputs,
    outcome: _Outcome,
    total: Decimal,
) -> list[ScheduledPayment]:
    """Split the total into the chosen installments, or one payment."""
    payment = inputs.context.payment
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


def _expiry(inputs: Inputs, outcome: _Outcome) -> datetime | None:
    moments = [
        revision.ends_at
        for revision in inputs.revisions
        if revision.id in outcome.applied and revision.ends_at is not None
    ]
    moments += [
        price.fresh_until
        for price in inputs.prices
        if price.fresh_until is not None and price.fresh_until > inputs.context.now
    ]
    for revision in inputs.revisions:
        if revision.starts_at is not None and revision.starts_at > inputs.context.now:
            moments.append(revision.starts_at)
        for leaf in leaves(revision.conditions.get("root")):
            if leaf.get("kind") != "calendar":
                continue
            local = inputs.context.now.astimezone(ZoneInfo(revision.timezone))
            for offset in (0, 1):
                day = local.date() + timedelta(days=offset)
                for boundary in ("00:00", leaf.get("start_time"), leaf.get("end_time")):
                    if boundary:
                        moment = datetime.combine(
                            day, time.fromisoformat(str(boundary)), local.tzinfo
                        )
                        if moment > inputs.context.now:
                            moments.append(moment)
    moments += [
        fact.expires_at
        for fact in (*inputs.shipping, *inputs.fees)
        if fact.expires_at is not None
    ]
    return min(moments) if moments else None


def _unique(decisions: list[Decision]) -> list[Decision]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Decision] = []
    for decision in decisions:
        key = (decision.subject, decision.status, decision.reason)
        if key not in seen:
            seen.add(key)
            unique.append(decision)
    return unique


def _empty(
    inputs: Inputs,
    decisions: list[Decision],
    missing: list[str],
    assumptions: list[str],
) -> PricingResult:
    """Return a result with no price: every total unknown, every reason kept."""
    context, policy = inputs.context, inputs.policy
    return PricingResult(
        scenario=policy.scenario,
        currency=context.currency,
        lines=context.lines,
        selected_prices=(),
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
        optimization_status=OptimizationStatus.COMPLETE,
    )


def canonical(value: object) -> object:
    """Turn inputs into JSON-ready data with a stable order."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: canonical(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {
            str(key): canonical(item) for key, item in sorted(value.items(), key=str)
        }
    if isinstance(value, (frozenset, set)):
        return sorted((canonical(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value if isinstance(value, (int, str, bool, type(None))) else str(value)


def fingerprint(inputs: Inputs) -> str:
    """Hash everything an evaluation read, including ``now``."""
    text = json.dumps(canonical(inputs), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


__all__ = ["CartLine", "Inputs", "canonical", "evaluate", "fingerprint"]
