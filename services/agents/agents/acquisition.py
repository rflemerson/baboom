"""Deterministic acquisition helpers for the API-first pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class SourcePageContext:
    """Normalized source-page context used by the ingestion asset."""

    item_id: int
    page_id: int
    page_url: str
    store_slug: str
    # JSON-encoded transport payloads from the backend API.
    source_page_api_context: str
    source_page_html_structured_data: str


@dataclass(frozen=True, slots=True)
class PreparedExtractionInputs:
    """Prepared API-backed inputs handed from acquisition into extraction."""

    origin_item_id: int
    page_url: str
    scraper_context: dict | None
    image_urls: list[str]
    fallback_reason: str


@dataclass(frozen=True, slots=True)
class ImageFilterConfig:
    """Deterministic URL-level filter configuration for image selection."""

    enabled: bool
    strip_query_for_dedupe: bool
    max_images: int
    exclude_keywords: tuple[str, ...]


class ItemInput(Protocol):
    """Minimal item config contract needed by acquisition helpers."""

    item_id: int
    url: str
    store_slug: str


class IngestionApi(Protocol):
    """Backend API surface needed by the acquisition helpers."""

    def get_scraped_item(self, item_id: int) -> dict | None:
        """Return one scraped item snapshot."""

    def ensure_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> dict | None:
        """Ensure the scraped item is linked to a source page."""


def get_item_or_raise(api: IngestionApi, item_id: int) -> dict:
    """Load one scraped item or fail fast."""
    item = api.get_scraped_item(item_id)
    if not item:
        message = f"Scraped item {item_id} not found"
        raise RuntimeError(message)
    return item


def resolve_source_page_context(
    api: IngestionApi,
    config: ItemInput,
    item: dict,
) -> SourcePageContext:
    """Ensure source page exists and return normalized page context."""
    item_id = config.item_id
    page_url = item.get("sourcePageUrl") or item.get("productLink") or config.url
    store_slug = item.get("storeSlug") or config.store_slug

    ensured_item = api.ensure_source_page(item_id, page_url, store_slug)
    if not ensured_item:
        message = f"Failed to ensure source page for item {item_id}"
        raise RuntimeError(message)

    page_id = ensured_item.get("sourcePageId")
    ensured_page_url = (
        ensured_item.get("sourcePageUrl")
        or item.get("sourcePageUrl")
        or item.get("productLink")
        or config.url
    )
    if not page_id:
        message = f"Missing sourcePageId for item {item_id}"
        raise RuntimeError(message)

    return SourcePageContext(
        item_id=int(ensured_item["id"]),
        page_id=int(page_id),
        page_url=ensured_page_url,
        store_slug=(
            ensured_item.get("storeSlug") or item.get("storeSlug") or config.store_slug
        ),
        source_page_api_context=(
            ensured_item.get("sourcePageApiContext")
            or item.get("sourcePageApiContext")
            or ""
        ),
        source_page_html_structured_data=(
            ensured_item.get("sourcePageHtmlStructuredData")
            or item.get("sourcePageHtmlStructuredData")
            or ""
        ),
    )


def build_download_result(page: SourcePageContext) -> dict:
    """Build the asset output payload from normalized page context."""
    return {
        "url": page.page_url,
        "page_id": page.page_id,
        "origin_item_id": page.item_id,
        "store_slug": page.store_slug,
        "source_page_api_context": page.source_page_api_context,
        "source_page_html_structured_data": page.source_page_html_structured_data,
    }


def build_prepared_extraction_inputs(
    *,
    downloaded_assets: dict,
) -> PreparedExtractionInputs:
    """Build the deterministic handoff between acquisition and extraction."""
    scraper_context = load_scraper_context(downloaded_assets)
    html_structured_data = load_html_structured_data(downloaded_assets)
    image_urls = extract_image_urls(
        scraper_context=scraper_context,
        html_structured_data=html_structured_data,
        filter_config=load_image_filter_config(),
    )
    fallback_reason = resolve_fallback_reason(image_urls)
    return PreparedExtractionInputs(
        origin_item_id=int(downloaded_assets["origin_item_id"]),
        page_url=downloaded_assets["url"],
        scraper_context=scraper_context,
        image_urls=image_urls,
        fallback_reason=fallback_reason,
    )


def load_scraper_context(downloaded_assets: dict) -> dict | None:
    """Parse JSON scraper context when source page payload is available."""
    return _load_json_object(downloaded_assets.get("source_page_api_context"))


def load_html_structured_data(downloaded_assets: dict) -> dict | None:
    """Parse HTML structured data when the API payload is available."""
    return _load_json_object(downloaded_assets.get("source_page_html_structured_data"))


def _load_json_object(raw_payload: str | None) -> dict | None:
    if not raw_payload:
        return None
    try:
        parsed_context = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    return parsed_context if isinstance(parsed_context, dict) else None


def extract_image_urls(
    *,
    scraper_context: dict | None,
    html_structured_data: dict | None = None,
    filter_config: ImageFilterConfig,
) -> list[str]:
    """Extract image URLs from API and HTML structured data in stable order."""
    image_urls: list[str] = []

    if scraper_context:
        image_urls.extend(_iter_image_urls(scraper_context))

    if html_structured_data:
        image_urls.extend(_iter_structured_data_image_urls(html_structured_data))

    return filter_image_urls(image_urls, config=filter_config)


def filter_image_urls(
    image_urls: list[str],
    *,
    config: ImageFilterConfig,
) -> list[str]:
    """Apply deterministic URL-level filters while preserving input order."""
    if not config.enabled:
        return image_urls[: config.max_images] if config.max_images > 0 else image_urls

    filtered_urls: list[str] = []
    seen_normalized_urls: set[str] = set()

    for image_url in image_urls:
        normalized_url = normalize_image_url(
            image_url,
            strip_query=config.strip_query_for_dedupe,
        )
        if normalized_url in seen_normalized_urls:
            continue
        if should_exclude_image_url(image_url, config):
            continue

        seen_normalized_urls.add(normalized_url)
        filtered_urls.append(image_url)
        if config.max_images > 0 and len(filtered_urls) >= config.max_images:
            break

    return filtered_urls


def load_image_filter_config() -> ImageFilterConfig:
    """Load deterministic image filtering rules from environment variables."""
    return ImageFilterConfig(
        enabled=_get_env_bool("AGENTS_IMAGE_FILTER_ENABLED", default=True),
        strip_query_for_dedupe=_get_env_bool(
            "AGENTS_IMAGE_FILTER_STRIP_QUERY_FOR_DEDUPE",
            default=True,
        ),
        max_images=max(0, _get_env_int("AGENTS_IMAGE_FILTER_MAX_IMAGES", 0)),
        exclude_keywords=_get_env_csv(
            "AGENTS_IMAGE_FILTER_EXCLUDE_KEYWORDS",
            (
                "logo",
                "icon",
                "placeholder",
                "avatar",
                "badge",
                "favicon",
            ),
        ),
    )


def should_exclude_image_url(image_url: str, config: ImageFilterConfig) -> bool:
    """Return whether one image URL should be dropped by keyword rules."""
    lowered_url = image_url.lower()
    return any(keyword in lowered_url for keyword in config.exclude_keywords)


def normalize_image_url(image_url: str, *, strip_query: bool) -> str:
    """Normalize one image URL for deterministic duplicate detection."""
    if not strip_query:
        return image_url.strip()

    split_url = urlsplit(image_url.strip())
    return urlunsplit(
        (split_url.scheme, split_url.netloc, split_url.path, "", ""),
    )


def _extract_image_url(image: object) -> str | None:
    if isinstance(image, str):
        url = image.strip()
        if not _is_likely_image_url(url):
            return None
        return url

    if not isinstance(image, dict):
        return None

    url = (
        image.get("src")
        or image.get("url")
        or image.get("imageUrl")
        or image.get("imageUrlHttps")
        or image.get("content")
    )
    if not url:
        return None
    normalized_url = str(url).strip()
    if not _is_likely_image_url(normalized_url):
        return None
    return normalized_url


def _is_likely_image_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False

    lowered = url.lower()
    return "ogp.me/ns" not in lowered and "w3.org/1999/xhtml/vocab" not in lowered


def _iter_image_urls(payload: object) -> list[str]:
    image_urls: list[str] = []
    _collect_image_urls(payload, image_urls)
    return image_urls


def _iter_structured_data_image_urls(payload: object) -> list[str]:
    image_urls: list[str] = []
    _collect_structured_data_image_urls(payload, image_urls)
    return image_urls


def _collect_image_urls(payload: object, image_urls: list[str]) -> None:
    if isinstance(payload, str):
        image_url = _extract_image_url(payload)
        if image_url:
            image_urls.append(image_url)
        return

    if isinstance(payload, dict):
        image_url = _extract_image_url(payload)
        if image_url:
            image_urls.append(image_url)
            return
        for value in payload.values():
            _collect_image_urls(value, image_urls)
        return

    if isinstance(payload, list):
        for item in payload:
            _collect_image_urls(item, image_urls)


def _collect_structured_data_image_urls(payload: object, image_urls: list[str]) -> None:
    if isinstance(payload, list):
        for item in payload:
            _collect_structured_data_image_urls(item, image_urls)
        return

    if not isinstance(payload, dict):
        return

    for key, value in payload.items():
        normalized_key = str(key).lower()
        if normalized_key in {
            "image",
            "images",
            "thumbnailurl",
            "contenturl",
            "og:image",
        }:
            _collect_image_urls(value, image_urls)
            continue

        if normalized_key == "properties" and isinstance(value, dict):
            og_image = value.get("og:image")
            if og_image is not None:
                _collect_image_urls(og_image, image_urls)
                nested_value = {
                    key: item for key, item in value.items() if key != "og:image"
                }
                _collect_structured_data_image_urls(nested_value, image_urls)
                continue

        _collect_structured_data_image_urls(value, image_urls)


def resolve_fallback_reason(image_urls: list[str]) -> str:
    """Return the extraction fallback reason for observability."""
    if image_urls:
        return ""
    return "no_images_available"


def _get_env_bool(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except ValueError:
        return default


def _get_env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    values = [value.strip().lower() for value in raw_value.split(",")]
    normalized_values = tuple(value for value in values if value)
    return normalized_values or default
