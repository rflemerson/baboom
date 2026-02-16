"""Dagster asset: extract consolidated metadata from downloaded source HTML."""

from dagster import AssetExecutionContext, asset

from ...schemas.product import RawScrapedData
from ..resources import AgentClientResource, ScraperServiceResource


@asset
def scraped_metadata(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
    downloaded_assets: dict,
) -> RawScrapedData:
    """Reads downloaded HTML and extracts lightweight metadata."""
    service = scraper.get_service()
    api = client.get_client()
    storage_path = downloaded_assets["storage_path"]
    page_url = downloaded_assets["url"]
    store_slug = downloaded_assets["store_slug"]
    origin_item_id = int(downloaded_assets["origin_item_id"])

    try:
        context.log.info(f"Extracting metadata from {storage_path}")
        meta_dict = service.extract_metadata(storage_path, page_url)
        raw_data = service.consolidate(meta_dict, brand_name_override=store_slug)
        context.add_output_metadata({"product_name": raw_data.name or "unknown"})
        return raw_data
    except Exception as e:
        context.log.error(f"Metadata extraction failed: {e}")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise
