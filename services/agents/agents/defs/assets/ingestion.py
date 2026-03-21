"""Dagster adapter for the deterministic source acquisition step."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from dagster import AssetExecutionContext, MetadataValue, asset

from ...acquisition.ingestion import (
    build_download_result,
    get_item_or_raise,
    resolve_source_page_context,
)

if TYPE_CHECKING:
    from ..config import ItemConfig
    from ..resources import AgentClientResource, ScraperServiceResource


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
        item = get_item_or_raise(api, config.item_id)
        page = resolve_source_page_context(api, config, item)
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
        return build_download_result(storage_path, page)
