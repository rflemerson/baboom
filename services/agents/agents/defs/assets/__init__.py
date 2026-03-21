"""Dagster asset adapters grouped by pipeline stage for the agents module."""

from ...extraction.image_selection import (
    is_potential_table_candidate,
    select_images_for_ocr,
)
from ...publishing.payload_utils import (
    build_nutrition_payload,
    slugify,
    to_graphql_stock_status,
)
from ..config import ItemConfig
from . import analysis, ingestion, metadata, ocr, publish
from .analysis import product_analysis
from .ingestion import downloaded_assets
from .metadata import scraped_metadata
from .ocr import ocr_extraction, prepared_extraction_inputs
from .publish import upload_to_api

ASSET_MODULES = [ingestion, metadata, ocr, analysis, publish]

__all__ = [
    "ASSET_MODULES",
    "ItemConfig",
    "build_nutrition_payload",
    "downloaded_assets",
    "is_potential_table_candidate",
    "ocr_extraction",
    "prepared_extraction_inputs",
    "product_analysis",
    "scraped_metadata",
    "select_images_for_ocr",
    "slugify",
    "to_graphql_stock_status",
    "upload_to_api",
]
