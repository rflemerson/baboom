"""Shared helpers for scraper spiders."""

from __future__ import annotations

import re
from typing import Any

from ..services import ScraperService


def is_http_url(value: str) -> bool:
    """Return True when value has an HTTP(S) scheme."""
    return value.startswith("http://") or value.startswith("https://")


def parse_positive_price(
    raw_price: Any,
    *,
    cents_for_int: bool = False,
    cents_for_digit_string: bool = False,
) -> float | None:
    """Parse positive numeric price values from mixed API payload formats."""
    value: float | None = None

    if raw_price is None:
        value = None
    elif isinstance(raw_price, int):
        value = float(raw_price) / 100.0 if cents_for_int else float(raw_price)
    elif isinstance(raw_price, float):
        value = raw_price
    else:
        raw = str(raw_price).strip()
        if not raw:
            return None
        if raw.isdigit():
            value = float(raw) / 100.0 if cents_for_digit_string else float(raw)
        else:
            normalized = raw.replace(",", ".")
            match = re.search(r"-?\d+(?:\.\d+)?", normalized)
            if match:
                try:
                    value = float(match.group(0))
                except (TypeError, ValueError):
                    value = None

    if value is None or value <= 0:
        return None
    return value


def parse_optional_int(value: Any) -> int | None:
    """Parse optional integer-like values from API payloads."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def persist_json_context(saved_item, context_payload: str) -> None:
    """Persist structured JSON context in source page when available."""
    ScraperService.persist_item_context(saved_item, context_payload)
