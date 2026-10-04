"""Evaluate a revision's condition tree to true, false or unknown.

``all``: a false child makes it false; otherwise any unknown makes it unknown.
``any``: a true child makes it true; otherwise any unknown makes it unknown.
``not``: flips true and false; unknown stays unknown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .types import Tri

if TYPE_CHECKING:
    from collections.abc import Callable

    from .types import OfferFact, PurchaseContext, RevisionRule


@dataclass(frozen=True)
class Amounts:
    """The subtotals a minimum can be measured on, per scope."""

    before_discounts: Decimal
    after_item_discounts: Decimal
    after_order_discounts: Decimal
    shipping: Decimal | None
    quantity: int


@dataclass(frozen=True)
class Evaluation:
    """The outcome of a tree and the leaves that decided it."""

    value: Tri
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ConditionInput:
    """What the leaves read."""

    context: PurchaseContext
    revision: RevisionRule
    offers: tuple[OfferFact, ...]
    qualifying: Amounts
    order: Amounts


def evaluate(tree: dict[str, object], data: ConditionInput) -> Evaluation:
    """Evaluate a ``{"root": ...}`` tree; no root is unconditional."""
    root = tree.get("root") if isinstance(tree, dict) else None
    if root is None:
        return Evaluation(Tri.TRUE, ())
    return _node(root, data)


def _node(node: object, data: ConditionInput) -> Evaluation:
    if not isinstance(node, dict):
        return Evaluation(Tri.UNKNOWN, ("malformed condition",))
    if "all" in node:
        return _combine([_node(child, data) for child in node["all"]], conj=True)
    if "any" in node:
        return _combine([_node(child, data) for child in node["any"]], conj=False)
    if "not" in node:
        inner = _node(node["not"], data)
        flipped = {Tri.TRUE: Tri.FALSE, Tri.FALSE: Tri.TRUE}.get(inner.value)
        return Evaluation(flipped or Tri.UNKNOWN, inner.reasons)
    leaf = LEAVES.get(str(node.get("kind")))
    if leaf is None:
        return Evaluation(Tri.UNKNOWN, (f"unsupported condition {node.get('kind')}",))
    return leaf(node, data)


def _combine(children: list[Evaluation], *, conj: bool) -> Evaluation:
    decisive = Tri.FALSE if conj else Tri.TRUE
    values = [child.value for child in children]
    reasons = tuple(reason for child in children for reason in child.reasons)
    if decisive in values:
        return Evaluation(decisive, reasons)
    if Tri.UNKNOWN in values:
        return Evaluation(Tri.UNKNOWN, reasons)
    return Evaluation(Tri.TRUE if conj else Tri.FALSE, reasons)


def _tri(*, holds: bool, reason: str) -> Evaluation:
    return Evaluation(Tri.TRUE if holds else Tri.FALSE, () if holds else (reason,))


def _unknown(reason: str) -> Evaluation:
    return Evaluation(Tri.UNKNOWN, (reason,))


def _amounts(leaf: dict, data: ConditionInput) -> Amounts:
    scope = leaf.get("scope")
    return data.qualifying if scope == "qualifying_items" else data.order


def _min_amount(leaf: dict, data: ConditionInput) -> Evaluation:
    if leaf.get("currency") != data.context.currency:
        return _unknown("minimum in another currency")
    amounts = _amounts(leaf, data)
    value = getattr(amounts, str(leaf.get("basis")), None)
    if not isinstance(value, Decimal):
        return _unknown("unsupported minimum basis")
    if leaf.get("includes_shipping"):
        if amounts.shipping is None:
            return _unknown("minimum includes shipping, which is not known")
        value += amounts.shipping
    minimum = Decimal(str(leaf.get("amount")))
    return _tri(holds=value >= minimum, reason=f"below the minimum of {minimum}")


def _min_quantity(leaf: dict, data: ConditionInput) -> Evaluation:
    needed = int(str(leaf.get("quantity")))
    quantity = _amounts(leaf, data).quantity
    return _tri(holds=quantity >= needed, reason=f"fewer than {needed} units")


def _all_offers(ids: set[int], attribute: str, data: ConditionInput) -> Evaluation:
    values = {getattr(offer, attribute) for offer in data.offers}
    if None in values:
        return _unknown(f"an offer's {attribute} is not known")
    return _tri(holds=values <= ids, reason=f"{attribute} outside the promotion")


def _channel(leaf: dict, data: ConditionInput) -> Evaluation:
    return _all_offers(set(leaf["channel_ids"]), "channel_id", data)


def _market(leaf: dict, data: ConditionInput) -> Evaluation:
    return _all_offers(set(leaf["market_ids"]), "market_id", data)


def _seller(leaf: dict, data: ConditionInput) -> Evaluation:
    return _all_offers(set(leaf["seller_account_ids"]), "seller_id", data)


def leaf_key(leaf: dict) -> str:
    """Name a condition leaf by its canonical content."""
    return json.dumps(leaf, sort_keys=True, default=str)


DESTINATION_FACT = "destination_fact"


def _destination(leaf: dict, data: ConditionInput) -> Evaluation:
    # A protected snapshot keeps the outcome of each destination leaf as a
    # fact, evaluated with the real destination before it was hidden.
    key = leaf_key(leaf)
    for claim in data.context.claims:
        if claim.kind == DESTINATION_FACT and claim.issuer == key:
            return _tri(holds=claim.value, reason="destination outside")
    destination = data.context.destination
    if destination is None:
        return _unknown("destination not given")
    if destination.country != leaf.get("country"):
        return _tri(holds=False, reason="destination country outside")
    return _combine(
        [
            _within(
                leaf.get("subdivisions") or [],
                destination.subdivision,
                "destination subdivision",
                exact=True,
            ),
            _within(
                leaf.get("postal_prefixes") or [],
                destination.postal_code.replace("-", "").replace(" ", "").upper(),
                "postal code",
                exact=False,
            ),
        ],
        conj=True,
    )


def _within(allowed: list, value: str, label: str, *, exact: bool) -> Evaluation:
    """Check a destination part against a list; an empty list allows anything."""
    if not allowed:
        return Evaluation(Tri.TRUE, ())
    if not value:
        return _unknown(f"{label} not given")
    if exact:
        holds = value in allowed
    else:
        holds = any(value.startswith(str(item).upper()) for item in allowed)
    return _tri(holds=holds, reason=f"{label} outside")


def _payment_method(leaf: dict, data: ConditionInput) -> Evaluation:
    payment = data.context.payment
    if payment is None:
        return _unknown("payment method not chosen")
    if payment.method not in leaf.get("codes", []):
        return _tri(holds=False, reason="another payment method")
    limit = leaf.get("max_installments")
    if limit is not None and payment.installments > int(str(limit)):
        return _tri(holds=False, reason="too many installments")
    return Evaluation(Tri.TRUE, ())


def _program_member(leaf: dict, data: ConditionInput) -> Evaluation:
    program = int(str(leaf["program_id"]))
    if program in data.context.programs:
        return Evaluation(Tri.TRUE, ())
    return _claimed("program_member", "program", program, data)


def _subscription(leaf: dict, data: ConditionInput) -> Evaluation:
    chosen = data.context.subscription
    if chosen is None:
        return _unknown("subscription not chosen")
    required = bool(leaf.get("required", True))
    return _tri(holds=chosen == required, reason="subscription differs")


def _new_customer(leaf: dict, data: ConditionInput) -> Evaluation:
    return _claimed(
        "new_customer",
        str(leaf.get("issuer")),
        int(str(leaf["issuer_id"])),
        data,
    )


def _claimed(
    kind: str, issuer: str, issuer_id: int, data: ConditionInput
) -> Evaluation:
    """Read a buyer's claim about an issuer; no claim is unknown."""
    for claim in data.context.claims:
        if (
            claim.kind == kind
            and claim.issuer == issuer
            and claim.issuer_id == issuer_id
        ):
            return _tri(holds=claim.value, reason=f"buyer states not {kind}")
    return _unknown(f"{kind} of {issuer} {issuer_id} not stated")


def _calendar(leaf: dict, data: ConditionInput) -> Evaluation:
    local = data.context.now.astimezone(ZoneInfo(data.revision.timezone))
    weekdays = leaf.get("weekdays") or []
    if weekdays and local.weekday() not in weekdays:
        return _tri(holds=False, reason="outside the promotion's weekdays")
    start, end = leaf.get("start_time"), leaf.get("end_time")
    moment = local.time()
    if start and moment < time.fromisoformat(str(start)):
        return _tri(holds=False, reason="before the promotion's hours")
    if end and moment >= time.fromisoformat(str(end)):
        return _tri(holds=False, reason="after the promotion's hours")
    return Evaluation(Tri.TRUE, ())


def _code_required(_leaf: dict, data: ConditionInput) -> Evaluation:
    codes = {code for _kind, code in data.revision.codes if code}
    if codes & data.context.codes:
        return Evaluation(Tri.TRUE, ())
    return _tri(holds=False, reason="code not entered")


LEAVES: dict[str, Callable[[dict, ConditionInput], Evaluation]] = {
    "min_amount": _min_amount,
    "min_quantity": _min_quantity,
    "channel": _channel,
    "market": _market,
    "seller": _seller,
    "destination": _destination,
    "payment_method": _payment_method,
    "program_member": _program_member,
    "subscription": _subscription,
    "new_customer": _new_customer,
    "calendar": _calendar,
    "code_required": _code_required,
}
