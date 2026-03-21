"""Dagster asset: ensure source page and store lightweight page artifacts."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from dagster import AssetExecutionContext, MetadataValue, asset

if TYPE_CHECKING:
    from ..resources import AgentClientResource, ScraperServiceResource
    from .shared import ItemConfig


class IngestionApi(Protocol):
    """Backend API surface needed by the ingestion asset helpers."""

    def get_scraped_item(self, item_id: int) -> dict | None:
        """Return one scraped item snapshot."""

    def ensure_source_page(
        self,
        item_id: int,
        url: str,
        store_slug: str,
    ) -> dict | None:
        """Ensure the scraped item is linked to a source page."""


@dataclass(frozen=True, slots=True)
class SourcePageContext:
    """Normalized source-page context used by the ingestion asset."""

    item_id: int
    page_id: int
    page_url: str
    store_slug: str
    source_page_raw_content: str
    source_page_content_type: str


def _get_item_or_raise(api: IngestionApi, item_id: int) -> dict:
    """Load the queued item or fail fast."""
    item = api.get_scraped_item(item_id)
    if not item:
        message = f"Scraped item {item_id} not found"
        raise RuntimeError(message)
    return item


def _resolve_source_page_context(
    api: IngestionApi,
    config: ItemConfig,
    item: dict,
) -> SourcePageContext:
    """Ensure source page exists and return normalized page context."""
    page_url = item.get("sourcePageUrl") or item.get("productLink") or config.url
    store_slug = item.get("storeSlug") or config.store_slug
    ensured_item = api.ensure_source_page(config.item_id, page_url, store_slug)
    if not ensured_item:
        message = f"Failed to ensure source page for item {config.item_id}"
        raise RuntimeError(message)

    page_id = ensured_item.get("sourcePageId")
    ensured_page_url = ensured_item.get("sourcePageUrl") or page_url
    if not page_id:
        message = f"Missing sourcePageId for item {config.item_id}"
        raise RuntimeError(message)

    return SourcePageContext(
        item_id=int(ensured_item["id"]),
        page_id=int(page_id),
        page_url=ensured_page_url,
        store_slug=ensured_item.get("storeSlug") or store_slug,
        source_page_raw_content=item.get("sourcePageRawContent") or "",
        source_page_content_type=item.get("sourcePageContentType") or "",
    )


def _build_download_result(storage_path: str, page: SourcePageContext) -> dict:
    """Build the asset output payload from normalized page context."""
    return {
        "storage_path": storage_path,
        "url": page.page_url,
        "page_id": page.page_id,
        "origin_item_id": page.item_id,
        "store_slug": page.store_slug,
        "source_page_raw_content": page.source_page_raw_content,
        "source_page_content_type": page.source_page_content_type,
    }


@asset
def downloaded_assets(
    context: AssetExecutionContext,
    config: ItemConfig,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
) -> dict:
    """Ensure page assets are downloaded and return page storage context."""
    service = scraper.get_service()
    api = client.get_client()

    try:
        started = time.perf_counter()
        item = _get_item_or_raise(api, config.item_id)
        page = _resolve_source_page_context(api, config, item)
        storage_path = service.download_assets(page.page_id, page.page_url)
        context.add_output_metadata(
            {
                "path": storage_path,
                "url": MetadataValue.url(page.page_url),
                "page_id": page.page_id,
                "origin_item_id": page.item_id,
                "scraper_context_type": page.source_page_content_type or "unknown",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
    except Exception as exc:
        context.log.exception("Download failed")
        api.report_error(config.item_id, str(exc), is_fatal=False)
        raise
    else:
        return _build_download_result(storage_path, page)
