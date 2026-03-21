"""Pure helpers backing the lightweight metadata asset."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ..contracts.acquisition import MetadataExtractionContext

if TYPE_CHECKING:
    from ..schemas.product import RawScrapedData


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


def build_metadata_extraction_context(
    downloaded_assets: dict,
) -> MetadataExtractionContext:
    """Normalize downloaded asset output into the metadata extraction contract."""
    return MetadataExtractionContext(
        storage_path=downloaded_assets["storage_path"],
        page_url=downloaded_assets["url"],
        store_slug=downloaded_assets["store_slug"],
        origin_item_id=int(downloaded_assets["origin_item_id"]),
    )


def extract_raw_metadata(
    service: MetadataService,
    extraction: MetadataExtractionContext,
) -> RawScrapedData:
    """Run metadata extraction and consolidation for one downloaded source page."""
    meta_dict = service.extract_metadata(extraction.storage_path, extraction.page_url)
    return service.consolidate(meta_dict, brand_name_override=extraction.store_slug)
