"""Shared helpers for scraper spiders."""

from __future__ import annotations

import re

from ..services import ScraperService

PRICE_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def is_http_url(value: str) -> bool:
    """Return True when value has an HTTP(S) scheme."""
    return value.startswith(("http://", "https://"))


def parse_positive_price(
    raw_price: object,
    *,
    cents_for_int: bool = False,
    cents_for_digit_string: bool = False,
) -> float | None:
    """Parse positive numeric price values from mixed API payload formats."""
    if raw_price is None:
        return None
    if isinstance(raw_price, int):
        value = float(raw_price) / 100.0 if cents_for_int else float(raw_price)
    elif isinstance(raw_price, float):
        value = raw_price
    else:
        value = _parse_string_price(
            str(raw_price),
            cents_for_digit_string=cents_for_digit_string,
        )

    if value is None or value <= 0:
        return None
    return value


def _parse_string_price(
    raw_price: str,
    *,
    cents_for_digit_string: bool,
) -> float | None:
    raw = raw_price.strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw) / 100.0 if cents_for_digit_string else float(raw)
    normalized = raw.replace(",", ".")
    match = PRICE_PATTERN.search(normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except (TypeError, ValueError):
        return None


def parse_optional_int(value: object) -> int | None:
    """Parse optional integer-like values from API payloads."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def persist_json_context(
    saved_item: object | None,
    context_payload: str,
    *,
    headers: dict[str, str] | None = None,
) -> None:
    """Persist structured JSON context in source page when available."""
    ScraperService.persist_page_context(
        saved_item,
        context_payload,
        headers=headers,
    )
