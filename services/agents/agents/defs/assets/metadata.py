"""Dagster adapter for the lightweight HTML metadata stage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dagster import AssetExecutionContext, asset

from ...acquisition.metadata import (
    build_metadata_extraction_context,
    extract_raw_metadata,
)

if TYPE_CHECKING:
    from ...schemas.product import RawScrapedData
    from ..resources import AgentClientResource, ScraperServiceResource


@asset
def scraped_metadata(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
    downloaded_assets: dict,
) -> RawScrapedData:
    """Read downloaded HTML and extract lightweight metadata."""
    service = scraper.get_service()
    api = client.get_client()
    extraction = build_metadata_extraction_context(downloaded_assets)

    try:
        context.log.info("Extracting metadata from %s", extraction.storage_path)
        raw_data = extract_raw_metadata(service, extraction)
        context.add_output_metadata({"product_name": raw_data.name or "unknown"})
    except Exception as exc:
        context.log.exception("Metadata extraction failed")
        api.report_error(extraction.origin_item_id, str(exc), is_fatal=False)
        raise
    else:
        return raw_data
