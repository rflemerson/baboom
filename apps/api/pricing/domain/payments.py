"""Enumerate how a buyer may pay when the context does not say."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .types import PaymentChoice

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .inputs import Inputs
    from .types import SelectedPrice


def payment_choices(
    inputs: Inputs,
    selected: Sequence[SelectedPrice],
) -> list[PaymentChoice | None]:
    """Return the ways to pay these base prices; ``None`` is "any method".

    A price of one method fixes that method and its installments. A price of
    any method, or paid at once, also allows each of the policy's cash
    methods, so "20% off with Pix" can apply on the full price. A price
    that states no payment allows only "any method", where conditions on a
    method stay unknown and never apply. Only the best scenario searches; a
    chosen payment is the only choice.
    """
    context, policy = inputs.context, inputs.policy
    if context.payment is not None or policy.scenario != "best":
        return [context.payment]
    found: set[PaymentChoice] = set()
    for price in selected:
        if price.payment_scope == "method":
            found.add(PaymentChoice(price.payment_method, price.installment_count or 1))
        elif price.payment_scope in {"any", "cash"}:
            found.update(PaymentChoice(method, 1) for method in policy.cash_methods)
    options = [None, *sorted(found, key=lambda item: (item.method, item.installments))]
    return [
        choice
        for choice in options
        if all(_accepts(price, choice) for price in selected)
    ]


def _accepts(price: SelectedPrice, choice: PaymentChoice | None) -> bool:
    """Tell whether a base price holds for this way of paying."""
    if price.payment_scope == "method":
        return (
            choice is not None
            and choice.method == price.payment_method
            and choice.installments == (price.installment_count or 1)
        )
    if price.payment_scope in {"any", "cash"}:
        return choice is None or choice.installments == 1
    return choice is None
