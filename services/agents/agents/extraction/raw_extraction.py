"""Run the multimodal raw extraction step from prepared deterministic inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..brain.raw_extraction_agent import run_raw_extraction
from .context_utils import build_json_context_block
from .image_selection import build_image_sequence_context

if TYPE_CHECKING:
    from ..contracts.acquisition import PreparedExtractionInputs
    from ..schemas.product import RawScrapedData


def run_raw_extraction_step(
    *,
    prepared_inputs: PreparedExtractionInputs,
    scraped_metadata: RawScrapedData,
) -> tuple[str, dict[str, Any]]:
    """Run multimodal extraction from a prepared acquisition payload."""
    sequence_context = build_image_sequence_context(
        prepared_inputs.candidates,
        prepared_inputs.image_paths,
    )
    llm_description = (
        (scraped_metadata.description or "")
        + sequence_context
        + build_json_context_block("SITE_DATA", prepared_inputs.site_data)
        + build_json_context_block("SCRAPER_CONTEXT", prepared_inputs.scraper_context)
    )
    raw_text = run_raw_extraction(
        name=scraped_metadata.name or prepared_inputs.page_url,
        description=llm_description,
        image_paths=prepared_inputs.image_paths,
    )
    return raw_text, build_raw_extraction_metadata(prepared_inputs=prepared_inputs)


def build_raw_extraction_metadata(
    *,
    prepared_inputs: PreparedExtractionInputs,
) -> dict[str, Any]:
    """Build Dagster metadata for the prepared raw extraction inputs."""
    return {
        "extraction_mode": prepared_inputs.extraction_mode,
        "fallback_reason": prepared_inputs.fallback_reason,
        "candidates_available": len(prepared_inputs.candidates),
        "scraper_context_included": bool(prepared_inputs.scraper_context),
        "images_used": len(prepared_inputs.image_paths),
        "images_sent": prepared_inputs.image_paths,
        "materialize_ms": prepared_inputs.materialize_ms,
    }
