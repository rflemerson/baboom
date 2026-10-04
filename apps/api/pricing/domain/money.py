"""Exact money: rounding to a currency's precision and allocating remainders."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
HUNDRED = Decimal(100)


def quantum(minor_unit: int) -> Decimal:
    """Return the smallest charged amount of a currency: 0.01 for two places."""
    return Decimal(1).scaleb(-minor_unit)


def round_money(amount: Decimal, minor_unit: int) -> Decimal:
    """Round to the currency's precision, half up as checkouts do."""
    return amount.quantize(quantum(minor_unit), rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, rate: Decimal) -> Decimal:
    """Return ``rate`` percent of ``amount``, unrounded."""
    return amount * rate / HUNDRED


def allocate(total: Decimal, weights: list[Decimal], minor_unit: int) -> list[Decimal]:
    """Split ``total`` over ``weights`` exactly, in the currency's precision.

    Shares are proportional to the weights, rounded down to the quantum; the
    remaining quanta go to the largest remainders, ties to the earliest
    weight. The shares always sum to ``total`` rounded to the quantum.
    """
    step = quantum(minor_unit)
    target = total.quantize(step, rounding=ROUND_HALF_EVEN)
    weight_sum = sum(weights, ZERO)
    if not weights:
        return []
    if weight_sum <= 0:
        shares = [ZERO] * len(weights)
        shares[0] = target
        return shares
    raw = [target * weight / weight_sum for weight in weights]
    floors = [(share // step) * step for share in raw]
    remaining = int((target - sum(floors, ZERO)) / step)
    order = sorted(
        range(len(weights)),
        key=lambda index: (-(raw[index] - floors[index]), index),
    )
    for index in order[:remaining]:
        floors[index] += step
    return floors
