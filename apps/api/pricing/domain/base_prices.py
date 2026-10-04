"""Select observed unit prices without applying promotions or reading mutable state."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from .types import Decision, DecisionStatus, SelectedPrice

if TYPE_CHECKING:
    from .engine import Inputs
    from .types import CartLine, OfferFact, PriceFact


# How many base-price combinations one evaluation tries. A single offer has
# a handful of prices; a large cart keeps only each line's cheapest beyond it.
MAX_BASE_CHOICES = 16


def price_options(
    inputs: Inputs,
    offers: dict[int, OfferFact],
    decisions: list[Decision],
    missing: list[str],
) -> list[list[SelectedPrice]] | None:
    """Return every usable base price per line, or report why there is none.

    Promotions are applied later to each choice: a dearer base price that
    still accepts a payment discount may end cheaper than one that already
    includes it, so no option is dropped here for being more expensive.
    """
    options: list[list[SelectedPrice]] = []
    for line in inputs.context.lines:
        refusal = _offer_refusal(offers.get(line.offer_id), line.offer_id, inputs)
        if refusal is not None:
            decisions.append(refusal)
            return None
        line_options = _base_options(inputs, line, decisions)
        if not line_options:
            missing.append(
                f"price of offer {line.offer_id} for {inputs.policy.scenario}"
            )
            return None
        options.append(line_options)
    return options


def base_choices(
    options: list[list[SelectedPrice]],
) -> tuple[list[tuple[SelectedPrice, ...]], bool]:
    """Return the base-price combinations to evaluate, and whether bounded.

    Beyond ``MAX_BASE_CHOICES`` each line keeps only its cheapest option.
    """
    total = 1
    for line_options in options:
        total *= len(line_options)
    if total <= MAX_BASE_CHOICES:
        return list(itertools.product(*options)), False
    return [tuple(line_options[0] for line_options in options)], True


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


def _base_options(
    inputs: Inputs,
    line: CartLine,
    decisions: list[Decision],
) -> list[SelectedPrice]:
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
    # Of prices that accept the same benefits, only the cheapest can win.
    cheapest: dict[tuple[object, ...], PriceFact] = {}
    for price in sorted(usable, key=lambda item: (item.amount, item.id)):
        cheapest.setdefault(
            (
                price.payment_scope,
                price.payment_method,
                price.installment_count,
                frozenset(price.included_adjustments),
            ),
            price,
        )
    return [
        SelectedPrice(
            offer_id=offer_id,
            observation_id=price.id,
            amount=price.amount,
            payment_method=price.payment_method,
            payment_scope=price.payment_scope,
            installment_count=price.installment_count,
            already_included=price.included_adjustments,
        )
        for price in cheapest.values()
    ]


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


def _fits_best(price: PriceFact, inputs: Inputs) -> bool:
    """Accept the store's price and every price paid at once: the buyer picks."""
    return _fits_listed(price, inputs) or _fits_cash(price, inputs)


SCENARIOS = {
    "listed": _fits_listed,
    "best": _fits_best,
    "cash": _fits_cash,
    "payment": _fits_payment,
}


def _fits_scenario(price: PriceFact, inputs: Inputs) -> bool:
    """Tell whether an observation is a base the scenario may use."""
    fits = SCENARIOS.get(inputs.policy.scenario)
    return fits is not None and fits(price, inputs)
