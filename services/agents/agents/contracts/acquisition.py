"""Contracts produced by the deterministic acquisition stage."""

from __future__ import annotations

from dataclasses import dataclass


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
class MetadataExtractionContext:
    """Normalized downloaded asset context needed for metadata extraction."""

    storage_path: str
    page_url: str
    store_slug: str
    origin_item_id: int


@dataclass(frozen=True, slots=True)
class PreparedExtractionInputs:
    """Prepared inputs handed from acquisition into the extraction stage."""

    origin_item_id: int
    page_url: str
    storage_path: str
    bucket: str
    scraper_context: dict | None
    site_data: dict | None
    candidates: list[dict]
    image_paths: list[str]
    extraction_mode: str
    fallback_reason: str
    materialize_ms: float
