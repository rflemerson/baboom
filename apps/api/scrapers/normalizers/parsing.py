"""Small parsing helpers shared by the pure payload normalizers."""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Literal

from ..contracts import CoverageInput

PRICE_PATTERN = re.compile(r"-?\d[\d.,]*")
CENTS = Decimal(100)
THOUSANDS_GROUP = 3
logger = logging.getLogger(__name__)


def is_http_url(value: str) -> bool:
    """Return True when value has an HTTP(S) scheme."""
    return value.startswith(("http://", "https://"))


def parse_positive_price(
    raw_price: object,
    *,
    cents_for_int: bool = False,
    cents_for_digit_string: bool = False,
) -> Decimal | None:
    """Parse a positive price to an exact decimal, or None.

    A JSON float becomes the decimal it was written as (``Decimal(repr)``), an
    integer or digit string may be cents, and a formatted string may use either
    comma or dot as the decimal separator, with the other as thousands.
    """
    if raw_price is None or isinstance(raw_price, bool):
        return None
    if isinstance(raw_price, int):
        value: Decimal | None = Decimal(raw_price)
        if cents_for_int:
            value = value / CENTS
    elif isinstance(raw_price, float):
        value = Decimal(repr(raw_price))
    elif isinstance(raw_price, Decimal):
        value = raw_price
    else:
        value = _parse_string_price(
            str(raw_price),
            cents_for_digit_string=cents_for_digit_string,
        )

    if value is None or not value.is_finite() or value <= 0:
        return None
    return value


def _parse_string_price(
    raw_price: str,
    *,
    cents_for_digit_string: bool,
) -> Decimal | None:
    raw = raw_price.strip()
    if not raw:
        return None
    if raw.isdigit():
        value = Decimal(raw)
        return value / CENTS if cents_for_digit_string else value
    match = PRICE_PATTERN.search(raw)
    if not match:
        return None
    number = match.group(0)
    decimal_separator = max(number.rfind(","), number.rfind("."))
    if decimal_separator >= 0 and _is_decimal_separator(number, decimal_separator):
        whole = re.sub(r"[.,]", "", number[:decimal_separator])
        number = f"{whole}.{number[decimal_separator + 1 :]}"
    else:
        number = re.sub(r"[.,]", "", number)
    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def _is_decimal_separator(number: str, position: int) -> bool:
    """Whether the last separator splits decimals rather than thousands.

    "1.234" with no other separator reads as thousands only when exactly three
    digits follow and the same mark does not appear earlier as a decimal; a
    different earlier mark ("1.234,56") makes the last one the decimal mark.
    """
    mark = number[position]
    other = "," if mark == "." else "."
    digits_after = len(number) - position - 1
    if other in number[:position]:
        return True
    if number.count(mark) > 1:
        return False
    return digits_after != THOUSANDS_GROUP


def parse_optional_int(value: object) -> int | None:
    """Parse optional integer-like values from API payloads."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def coverage(
    dimension: Literal[
        "variants",
        "sellers",
        "offers",
        "payment_prices",
        "availability",
        "pagination",
    ],
    *,
    complete: bool,
    reason: str = "",
) -> CoverageInput:
    """Return how completely a page's normalizer read one dimension."""
    return CoverageInput(
        dimension=dimension,
        status="complete" if complete else "partial",
        reason=reason,
    )
