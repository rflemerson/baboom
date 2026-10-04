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
from decimal import Decimal
from typing import TYPE_CHECKING

from .conditions import Amounts, ConditionInput
from .conditions import evaluate as evaluate_conditions
from .effects import (
    STAGES,
    SUPPORTED_EFFECTS,
    Environment,
    LineState,
    apply_effect,
    unsupported_limits,
)
from .money import ZERO, allocate, round_money
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
    from datetime import datetime

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
REWARD_KINDS = frozenset({"cashback", "points"})


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
    # "included_in_prices": the market's prices carry every tax; "consulted":
    # ``fees`` lists every charge a source quoted; "not_consulted": nobody
    # asked, so taxes and fees are unknown, not zero.
    fees_status: str = "not_consulted"


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


def evaluate(inputs: Inputs) -> PricingResult:
    """Return the scenario's result for these inputs and this ``now``."""
    context, policy = inputs.context, inputs.policy
    decisions: list[Decision] = []
    missing: list[str] = []
    assumptions: list[str] = []
    offers = {offer.id: offer for offer in inputs.offers}

    selected = _select_prices(inputs, offers, decisions, missing)
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
        key = (
            _comparable_total(outcome),
            -_money_rewards(outcome),
            -len(outcome.applied),
        )
        if best_key is None or key < best_key:
            best, best_key = outcome, key
    if best is None:  # pragma: no cover - the empty subset always exists
        return _empty(inputs, decisions, missing, assumptions)
    decisions += _unapplied(candidates, best, alone)
    best.decisions[:0] = decisions
    best.missing[:0] = missing
    best.assumptions[:0] = assumptions
    return _result(inputs, selected, best, status)


# Base prices


def _select_prices(
    inputs: Inputs,
    offers: dict[int, OfferFact],
    decisions: list[Decision],
    missing: list[str],
) -> list[SelectedPrice] | None:
    """Choose one base price per line, or report why the scenario has none."""
    chosen: list[SelectedPrice] = []
    for line in inputs.context.lines:
        refusal = _offer_refusal(offers.get(line.offer_id), line.offer_id, inputs)
        if refusal is not None:
            decisions.append(refusal)
            return None
        price = _base_price(inputs, line, decisions)
        if price is None:
            missing.append(
                f"price of offer {line.offer_id} for {inputs.policy.scenario}"
            )
            return None
        chosen.append(price)
    return chosen


def _offer_refusal(
    offer: OfferFact | None,
    offer_id: int,
    inputs: Inputs,
) -> Decision | None:
    """Return why an offer cannot be priced in this context, or None."""
    subject = f"offer {offer_id}"
    if offer is None:
        return Decision(subject, DecisionStatus.UNKNOWN, "offer not given")
    checks = (
        (
            not offer.access_available,
            DecisionStatus.ACCESS_UNAVAILABLE,
            "source unavailable",
        ),
        (not offer.purchasable, DecisionStatus.INELIGIBLE, "not purchasable"),
        (
            offer.market_id != inputs.context.market_id,
            DecisionStatus.INELIGIBLE,
            "another market",
        ),
    )
    return next(
        (Decision(subject, status, text) for failed, status, text in checks if failed),
        None,
    )


PUBLIC_STAGES = frozenset({"catalog", "product_page"})


def _restriction(price: PriceFact, quantity: int) -> tuple[DecisionStatus, str] | None:
    """Return why an observed price cannot be one unit's public price here.

    A price for a quantity range, a line or an order, a cart or checkout
    stage, or any observed context (membership, destination, programme) the
    engine cannot match yet is never applied as a universal unit price.
    """
    if quantity < price.quantity_min or (
        price.quantity_max is not None and quantity > price.quantity_max
    ):
        return DecisionStatus.INELIGIBLE, "quantity outside the price's range"
    if price.amount_basis != "unit":
        return DecisionStatus.UNSUPPORTED, f"price is per {price.amount_basis}"
    if price.capture_stage not in PUBLIC_STAGES:
        return DecisionStatus.UNKNOWN, f"price quoted at the {price.capture_stage}"
    if price.context:
        keys = sorted(key for key, _value in price.context)
        return DecisionStatus.UNKNOWN, f"price restricted to context {keys}"
    return None


def _base_price(
    inputs: Inputs,
    line: CartLine,
    decisions: list[Decision],
) -> SelectedPrice | None:
    context, policy = inputs.context, inputs.policy
    offer_id = line.offer_id
    usable: list[PriceFact] = []
    for price in inputs.prices:
        if price.offer_id != offer_id or price.role != "payable":
            continue
        if price.currency != context.currency:
            continue
        if price.semantics not in policy.accepted_semantics:
            continue
        if price.evidence_level not in policy.accepted_evidence:
            continue
        if price.fresh_until is not None and price.fresh_until <= context.now:
            decisions.append(
                Decision(
                    f"price {price.id}", DecisionStatus.STALE, "past its freshness"
                ),
            )
            continue
        restriction = _restriction(price, line.quantity)
        if restriction is not None:
            decisions.append(Decision(f"price {price.id}", *restriction))
            continue
        if _fits_scenario(price, inputs):
            usable.append(price)
    if not usable:
        return None
    price = min(usable, key=lambda item: (item.amount, item.id))
    return SelectedPrice(
        offer_id=offer_id,
        observation_id=price.id,
        amount=price.amount,
        payment_method=price.payment_method,
        payment_scope=price.payment_scope,
        installment_count=price.installment_count,
        already_included=price.included_adjustments,
    )


def _single_payment(price: PriceFact) -> bool:
    """Tell whether a price is one payment, with no installment plan."""
    return price.installment_count in (None, 1)


def _unstated(price: PriceFact) -> bool:
    """Tell whether a price states no payment and no installments."""
    return price.payment_scope == "unknown" and price.installment_count is None


def _universal(price: PriceFact) -> bool:
    """Tell whether a price holds for any payment method, paid at once."""
    return price.payment_scope == "any" and _single_payment(price)


def _fits_listed(price: PriceFact, _inputs: Inputs) -> bool:
    """Accept the store's price: unstated, or stated valid for any method."""
    return _unstated(price) or _universal(price)


def _fits_cash(price: PriceFact, inputs: Inputs) -> bool:
    """Accept a price paid at once: cash, a cash method, any method, or unstated."""
    policy = inputs.policy
    if price.payment_scope == "cash" or _universal(price):
        return True
    if price.payment_scope == "method":
        return _single_payment(price) and price.payment_method in policy.cash_methods
    return _unstated(price) and policy.include_unknown_payment


def _fits_payment(price: PriceFact, inputs: Inputs) -> bool:
    """Accept the chosen method and count, or a single payment any method takes."""
    payment = inputs.context.payment
    if payment is None:
        return False
    if price.payment_scope == "method":
        count = price.installment_count or 1
        return price.payment_method == payment.method and count == payment.installments
    if payment.installments != 1:
        return False
    return _universal(price) or (
        _unstated(price) and inputs.policy.include_unknown_payment
    )


SCENARIOS = {"listed": _fits_listed, "cash": _fits_cash, "payment": _fits_payment}


def _fits_scenario(price: PriceFact, inputs: Inputs) -> bool:
    """Tell whether an observation is a base the scenario may use."""
    fits = SCENARIOS.get(inputs.policy.scenario)
    return fits is not None and fits(price, inputs)


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
    limits = [problem for e in revision.effects for problem in unsupported_limits(e)]
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


def _leaves(node: object) -> list[object]:
    if not isinstance(node, dict):
        return []
    for key in ("all", "any"):
        if key in node:
            return [leaf for child in node[key] for leaf in _leaves(child)]
    if "not" in node:
        return _leaves(node["not"])
    return [node]


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
    if not any(_targets(revision, line.offer) for line in lines):
        return DecisionStatus.INELIGIBLE, "targets none of these offers"
    if _payment_already_included(revision, lines):
        return DecisionStatus.CONFLICT, "payment discount already in the price"
    return None


def _leaf_kinds(node: object) -> set[str]:
    if not isinstance(node, dict):
        return set()
    for key in ("all", "any"):
        if key in node:
            return set().union(*(_leaf_kinds(child) for child in node[key]))
    if "not" in node:
        return _leaf_kinds(node["not"])
    return {str(node.get("kind"))}


def _payment_already_included(revision: RevisionRule, lines: list[LineState]) -> bool:
    """Tell whether a payment discount would repeat one already in the price."""
    payment_effects = [e for e in revision.effects if e.stage == "payment"]
    if not payment_effects:
        return False
    targeted = [line for line in lines if _targets(revision, line.offer)]
    return bool(targeted) and all(
        "payment_discount" in line.price.already_included for line in targeted
    )


def _matches(
    scope_kind: str, ref_id: int | None, external: str, offer: OfferFact
) -> bool:
    values = {
        "offer": offer.id,
        "listing": offer.listing_id,
        "listing_variant": offer.listing_variant_id,
        "seller_account": offer.seller_id,
        "market": offer.market_id,
        "channel": offer.channel_id,
        "product": offer.product_id,
        "brand": offer.brand_id,
        "merchant": offer.merchant_id,
    }
    if scope_kind == "category":
        return ref_id in offer.category_ids
    if scope_kind == "external_category":
        return external in offer.external_categories
    return values.get(scope_kind) == ref_id and ref_id is not None


def _in_role(revision: RevisionRule, role: str, offer: OfferFact) -> bool | None:
    """Whether an offer is in a role's scope; None when the role names nothing."""
    rows = [scope for scope in revision.scopes if scope.role == role]
    if not rows:
        return None
    for scope in rows:
        if scope.mode == "exclude" and _matches(
            scope.kind, scope.ref_id, scope.external_ref, offer
        ):
            return False
    includes = [scope for scope in rows if scope.mode == "include"]
    if not includes:
        return True
    by_kind: dict[str, bool] = {}
    for scope in includes:
        hit = _matches(scope.kind, scope.ref_id, scope.external_ref, offer)
        by_kind[scope.kind] = by_kind.get(scope.kind, False) or hit
    if any(scope.combine == "intersection" for scope in includes):
        return all(by_kind.values())
    return any(by_kind.values())


def _targets(revision: RevisionRule, offer: OfferFact) -> bool:
    """Whether the revision's benefit reaches an offer."""
    return bool(_in_role(revision, "target", offer))


def _qualifies(revision: RevisionRule, offer: OfferFact) -> bool:
    """Whether an offer counts toward the revision's conditions."""
    explicit = _in_role(revision, "qualification", offer)
    return _targets(revision, offer) if explicit is None else explicit


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
        _targets,
        inputs.policy.assume_full_caps,
        inputs.routes,
    )
    _shipping(inputs, outcome)
    initial = {line.offer.id: line.initial for line in lines}
    checkpoints: dict[str, dict[int, Decimal]] = {}
    held: dict[int, Tri] = {}
    for stage in STAGES:
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

    qualifying = [line for line in outcome.lines if _qualifies(revision, line.offer)]
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


def _shipping(inputs: Inputs, outcome: _Outcome) -> None:
    """Read the known shipping of every checkout group, or mark it unknown."""
    groups = inputs.context.groups or ()
    keys = [group.key for group in groups] or ["all"]
    quotes = {quote.group_key: quote for quote in inputs.shipping}
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


def _comparable_total(outcome: _Outcome) -> Decimal:
    """Return what a combination costs now: merchandise, and shipping if known."""
    merchandise = sum((line.current for line in outcome.lines), ZERO)
    return merchandise + (outcome.shipping or ZERO)


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
    if inputs.fees_status == "not_consulted" and not inputs.fees:
        return None, ["taxes and fees not consulted"]
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
