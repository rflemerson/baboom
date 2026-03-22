"""Deterministic acquisition helpers for the API-first pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SourcePageContext:
    """Normalized source-page context used by the ingestion asset."""

    item_id: int
    page_id: int
    page_url: str
    store_slug: str
    source_page_raw_content: str
    source_page_content_type: str


@dataclass(frozen=True, slots=True)
class PreparedExtractionInputs:
    """Prepared API-backed inputs handed from acquisition into extraction."""

    origin_item_id: int
    page_url: str
    scraper_context: dict | None
    image_urls: list[str]
    fallback_reason: str


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


def ensure_item_source_page(
    api: IngestionApi,
    *,
    item_id: int,
    fallback_url: str,
    fallback_store_slug: str,
) -> tuple[dict, dict]:
    """Load one item, ensure its source page, and return both payloads."""
    item = get_item_or_raise(api, item_id)
    page_url = item.get("sourcePageUrl") or item.get("productLink") or fallback_url
    store_slug = item.get("storeSlug") or fallback_store_slug
    ensured_item = api.ensure_source_page(item_id, page_url, store_slug)
    if not ensured_item:
        message = f"Failed to ensure source page for item {item_id}"
        raise RuntimeError(message)
    return item, ensured_item


def resolve_source_page_context(
    api: IngestionApi,
    config: ItemInput,
    item: dict,
) -> SourcePageContext:
    """Ensure source page exists and return normalized page context."""
    current_item, ensured_item = ensure_item_source_page(
        api,
        item_id=config.item_id,
        fallback_url=config.url,
        fallback_store_slug=config.store_slug,
    )

    page_id = ensured_item.get("sourcePageId")
    ensured_page_url = (
        ensured_item.get("sourcePageUrl")
        or current_item.get("sourcePageUrl")
        or current_item.get("productLink")
        or config.url
    )
    if not page_id:
        message = f"Missing sourcePageId for item {config.item_id}"
        raise RuntimeError(message)

    return SourcePageContext(
        item_id=int(ensured_item["id"]),
        page_id=int(page_id),
        page_url=ensured_page_url,
        store_slug=(
            ensured_item.get("storeSlug")
            or item.get("storeSlug")
            or current_item.get("storeSlug")
            or config.store_slug
        ),
        source_page_raw_content=(
            ensured_item.get("sourcePageRawContent")
            or item.get("sourcePageRawContent")
            or current_item.get("sourcePageRawContent")
            or ""
        ),
        source_page_content_type=(
            ensured_item.get("sourcePageContentType")
            or item.get("sourcePageContentType")
            or current_item.get("sourcePageContentType")
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
        "source_page_raw_content": page.source_page_raw_content,
        "source_page_content_type": page.source_page_content_type,
    }


def build_prepared_extraction_inputs(
    *,
    downloaded_assets: dict,
) -> PreparedExtractionInputs:
    """Build the deterministic handoff between acquisition and extraction."""
    scraper_context = load_scraper_context(downloaded_assets)
    image_urls = extract_image_urls(scraper_context)
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
    raw_scraper_context = downloaded_assets.get("source_page_raw_content")
    scraper_context_type = str(
        downloaded_assets.get("source_page_content_type") or "",
    ).upper()
    if not raw_scraper_context or scraper_context_type != "JSON":
        return None
    try:
        parsed_context = json.loads(raw_scraper_context)
    except json.JSONDecodeError:
        return None
    return parsed_context if isinstance(parsed_context, dict) else None


def extract_image_urls(scraper_context: dict | None) -> list[str]:
    """Extract image URLs from the API payload while preserving source order."""
    if not scraper_context:
        return []
    return list(_iter_image_urls(scraper_context))


def _extract_image_url(image: object) -> str | None:
    if isinstance(image, str):
        url = image.strip()
        if not url:
            return None
        return url

    if not isinstance(image, dict):
        return None

    url = (
        image.get("src")
        or image.get("url")
        or image.get("imageUrl")
        or image.get("imageUrlHttps")
    )
    if not url:
        return None
    return str(url)


def _iter_image_urls(payload: object) -> list[str]:
    image_urls: list[str] = []
    _collect_image_urls(payload, image_urls)
    return image_urls


def _collect_image_urls(payload: object, image_urls: list[str]) -> None:
    if isinstance(payload, dict):
        if "images" in payload and isinstance(payload["images"], list):
            for image in payload["images"]:
                image_url = _extract_image_url(image)
                if image_url:
                    image_urls.append(image_url)
            return
        for value in payload.values():
            _collect_image_urls(value, image_urls)
        return

    if isinstance(payload, list):
        for item in payload:
            _collect_image_urls(item, image_urls)


def resolve_fallback_reason(image_urls: list[str]) -> str:
    """Return the extraction fallback reason for observability."""
    if image_urls:
        return ""
    return "no_images_available"
