"""Dagster asset: extract consolidated metadata from downloaded source HTML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from dagster import AssetExecutionContext, asset

if TYPE_CHECKING:
    from ...schemas.product import RawScrapedData
    from ..resources import AgentClientResource, ScraperServiceResource


class MetadataService(Protocol):
    """Scraper service surface needed by the metadata asset helpers."""

    def extract_metadata(self, storage_path: str, page_url: str) -> dict:
        """Extract raw metadata from one persisted page artifact."""

    def consolidate(
        self,
        metadata: dict,
        *,
        brand_name_override: str | None = None,
    ) -> RawScrapedData:
        """Consolidate raw metadata into the normalized schema."""


@dataclass(frozen=True, slots=True)
class MetadataExtractionContext:
    """Normalized downloaded asset context needed for metadata extraction."""

    storage_path: str
    page_url: str
    store_slug: str
    origin_item_id: int


def _build_metadata_extraction_context(
    downloaded_assets: dict,
) -> MetadataExtractionContext:
    """Normalize downloaded asset output into the metadata extraction contract."""
    return MetadataExtractionContext(
        storage_path=downloaded_assets["storage_path"],
        page_url=downloaded_assets["url"],
        store_slug=downloaded_assets["store_slug"],
        origin_item_id=int(downloaded_assets["origin_item_id"]),
    )


def _extract_raw_metadata(
    service: MetadataService,
    extraction: MetadataExtractionContext,
) -> RawScrapedData:
    """Run metadata extraction and consolidation for one downloaded source page."""
    meta_dict = service.extract_metadata(extraction.storage_path, extraction.page_url)
    return service.consolidate(meta_dict, brand_name_override=extraction.store_slug)


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
    extraction = _build_metadata_extraction_context(downloaded_assets)

    try:
        context.log.info("Extracting metadata from %s", extraction.storage_path)
        raw_data = _extract_raw_metadata(service, extraction)
        context.add_output_metadata({"product_name": raw_data.name or "unknown"})
    except Exception as exc:
        context.log.exception("Metadata extraction failed")
        api.report_error(extraction.origin_item_id, str(exc), is_fatal=False)
        raise
    else:
        return raw_data
