"""Helpers that prepare captured source data for extraction."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING
from urllib.parse import urljoin

if TYPE_CHECKING:
    from collections.abc import Iterable

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")


def parse_json_maybe(value: object) -> object | None:
    """Parse a JSON string or return already structured data unchanged."""
    if not value:
        return None

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    return None


def iter_values(payload: object) -> Iterable[object]:
    """Yield every nested value in a mapping or sequence."""
    if isinstance(payload, dict):
        for value in payload.values():
            yield value
            yield from iter_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield item
            yield from iter_values(item)


def looks_like_image_url(value: str) -> bool:
    """Return whether a string has a supported image URL shape."""
    lower = value.lower().split("?")[0]

    if not lower.startswith(("http://", "https://", "//", "/")):
        return False

    return lower.endswith(IMAGE_EXTENSIONS)


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Resolve protocol-relative and relative URLs against a base URL."""
    if url.startswith("//"):
        return "https:" + url

    if base_url and not url.startswith(("http://", "https://")):
        return urljoin(base_url, url)

    return url


def extract_image_urls_from_payload(
    payload: object,
    base_url: str | None = None,
) -> list[str]:
    """Extract unique image URLs from recursively nested payload data."""
    urls = [
        normalize_url(value, base_url=base_url)
        for value in iter_values(payload)
        if isinstance(value, str) and looks_like_image_url(value)
    ]
    return list(dict.fromkeys(urls))


def extract_image_urls_from_html_text(
    value: str | None,
    base_url: str | None = None,
) -> list[str]:
    """Extract unique image URLs from arbitrary HTML or text content."""
    if not value:
        return []

    extensions = "|".join(ext.lstrip(".") for ext in IMAGE_EXTENSIONS)
    matches = re.findall(
        rf'https?://[^\s"\']+\.(?:{extensions})(?:\?[^\s"\']*)?',
        value,
        flags=re.IGNORECASE,
    )
    return list(dict.fromkeys(normalize_url(url, base_url=base_url) for url in matches))


def build_prepared_context(item: dict[str, object]) -> dict[str, object]:
    """Combine captured fields and discovered image URLs for one item."""
    base_url = item.get("sourcePageUrl") or item.get("productLink")

    api_context = parse_json_maybe(item.get("sourcePageContext"))
    structured_data = parse_json_maybe(item.get("sourcePageStructuredData"))

    image_urls: list[str] = list(item.get("imageUrls") or [])

    image_urls.extend(extract_image_urls_from_payload(api_context, base_url=base_url))
    image_urls.extend(
        extract_image_urls_from_payload(structured_data, base_url=base_url),
    )

    image_urls = list(dict.fromkeys(image_urls))

    return {
        "itemId": item.get("id"),
        "storeSlug": item.get("storeSlug"),
        "sourcePageUrl": item.get("sourcePageUrl"),
        "productLink": item.get("productLink"),
        "name": item.get("name"),
        "price": item.get("price"),
        "stockStatus": item.get("stockStatus"),
        "imageUrls": image_urls,
        "apiContext": api_context,
        "structuredData": structured_data,
    }
