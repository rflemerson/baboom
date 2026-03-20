"""Dagster asset: ensure source page and store lightweight page artifacts."""

import time

from dagster import AssetExecutionContext, MetadataValue, asset

from ..resources import AgentClientResource, ScraperServiceResource
from .shared import ItemConfig


@asset
def downloaded_assets(
    context: AssetExecutionContext,
    config: ItemConfig,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
) -> dict:
    """Ensures page assets are downloaded and returns page storage context."""
    service = scraper.get_service()
    api = client.get_client()

    try:
        started = time.perf_counter()
        item = api.get_scraped_item(config.item_id)
        if not item:
            raise RuntimeError(f"Scraped item {config.item_id} not found")

        page_url = item.get("sourcePageUrl") or item.get("productLink") or config.url
        store_slug = item.get("storeSlug") or config.store_slug
        ensured_item = api.ensure_source_page(config.item_id, page_url, store_slug)
        if not ensured_item:
            raise RuntimeError(
                f"Failed to ensure source page for item {config.item_id}",
            )

        page_id = ensured_item.get("sourcePageId")
        ensured_page_url = ensured_item.get("sourcePageUrl") or page_url
        if not page_id:
            raise RuntimeError(f"Missing sourcePageId for item {config.item_id}")

        storage_path = service.download_assets(int(page_id), ensured_page_url)
        source_page_raw_content = item.get("sourcePageRawContent") or ""
        source_page_content_type = item.get("sourcePageContentType") or ""
        context.add_output_metadata(
            {
                "path": storage_path,
                "url": MetadataValue.url(ensured_page_url),
                "page_id": int(page_id),
                "origin_item_id": int(ensured_item["id"]),
                "scraper_context_type": source_page_content_type or "unknown",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return {
            "storage_path": storage_path,
            "url": ensured_page_url,
            "page_id": int(page_id),
            "origin_item_id": int(ensured_item["id"]),
            "store_slug": ensured_item.get("storeSlug") or store_slug,
            "source_page_raw_content": source_page_raw_content,
            "source_page_content_type": source_page_content_type,
        }
    except Exception as e:
        context.log.error(f"Download failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise
