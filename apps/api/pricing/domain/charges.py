"""Add up the taxes and fees an evaluation was given."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .money import ZERO, round_money

if TYPE_CHECKING:
    from decimal import Decimal

    from .inputs import Inputs


def fee_total(inputs: Inputs) -> tuple[Decimal | None, list[str]]:
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
