import json
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")


def parse_json_maybe(value: Any) -> Any:
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


def iter_values(payload: Any) -> Iterable[Any]:
    if isinstance(payload, dict):
        for value in payload.values():
            yield value
            yield from iter_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield item
            yield from iter_values(item)


def looks_like_image_url(value: str) -> bool:
    lower = value.lower().split("?")[0]

    if not lower.startswith(("http://", "https://", "//", "/")):
        return False

    return lower.endswith(IMAGE_EXTENSIONS)


def normalize_url(url: str, base_url: str | None = None) -> str:
    if url.startswith("//"):
        return "https:" + url

    if base_url and not url.startswith(("http://", "https://")):
        return urljoin(base_url, url)

    return url


def extract_image_urls_from_payload(
    payload: Any, base_url: str | None = None
) -> list[str]:
    urls: list[str] = []

    for value in iter_values(payload):
        if isinstance(value, str) and looks_like_image_url(value):
            urls.append(normalize_url(value, base_url=base_url))

    seen = set()
    result = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


def extract_image_urls_from_html_text(
    value: str | None, base_url: str | None = None
) -> list[str]:
    if not value:
        return []

    extensions = "|".join(ext.lstrip(".") for ext in IMAGE_EXTENSIONS)
    matches = re.findall(
        rf'https?://[^\s"\']+\.(?:{extensions})(?:\?[^\s"\']*)?',
        value,
        flags=re.IGNORECASE,
    )
    return list(dict.fromkeys(normalize_url(url, base_url=base_url) for url in matches))


def build_prepared_context(item: dict[str, Any]) -> dict[str, Any]:
    base_url = item.get("sourcePageUrl") or item.get("productLink")

    api_context = parse_json_maybe(item.get("sourcePageApiContext"))
    structured_data = parse_json_maybe(item.get("sourcePageHtmlStructuredData"))

    image_urls: list[str] = []

    image_urls.extend(extract_image_urls_from_payload(api_context, base_url=base_url))
    image_urls.extend(
        extract_image_urls_from_payload(structured_data, base_url=base_url)
    )

    if isinstance(item.get("sourcePageHtmlStructuredData"), str):
        image_urls.extend(
            extract_image_urls_from_html_text(
                item.get("sourcePageHtmlStructuredData"),
                base_url=base_url,
            ),
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
