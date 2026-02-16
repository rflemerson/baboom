"""Dagster assets split by pipeline stage for the agents module."""

from . import analysis, ingestion, metadata, ocr, publish
from .analysis import product_analysis
from .ingestion import downloaded_assets
from .metadata import scraped_metadata
from .ocr import ocr_extraction
from .publish import upload_to_api
from .shared import (
    ItemConfig,
    _build_nutrition_payload,
    _is_potential_table_candidate,
    _select_images_for_ocr,
    _slugify,
    _to_graphql_stock_status,
)

ASSET_MODULES = [ingestion, metadata, ocr, analysis, publish]

__all__ = [
    "ASSET_MODULES",
    "ItemConfig",
    "_build_nutrition_payload",
    "_is_potential_table_candidate",
    "_select_images_for_ocr",
    "_slugify",
    "_to_graphql_stock_status",
    "downloaded_assets",
    "ocr_extraction",
    "product_analysis",
    "scraped_metadata",
    "upload_to_api",
]
