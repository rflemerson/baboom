"""Dagster adapters for prepared extraction inputs and raw OCR extraction."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from dagster import AssetExecutionContext, MetadataValue, asset

from ...acquisition.prepared_inputs import build_prepared_extraction_inputs
from ...extraction.raw_extraction import (
    run_raw_extraction_step,
)

if TYPE_CHECKING:
    from ...contracts.acquisition import PreparedExtractionInputs
    from ...schemas.product import RawScrapedData
    from ..resources import (
        AgentClientResource,
        ScraperServiceResource,
        StorageResource,
    )


@asset
def prepared_extraction_inputs(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    storage: StorageResource,
    downloaded_assets: dict,
    scraped_metadata: RawScrapedData,
) -> PreparedExtractionInputs:
    """Prepare deterministic OCR inputs from stored page artifacts."""
    store = storage.get_storage()
    service = scraper.get_service()
    prepared_inputs = build_prepared_extraction_inputs(
        store=store,
        service=service,
        downloaded_assets=downloaded_assets,
        scraped_metadata=scraped_metadata,
    )
    context.add_output_metadata(
        {
            "bucket": prepared_inputs.bucket,
            "page_url": MetadataValue.url(prepared_inputs.page_url),
            "candidates_available": len(prepared_inputs.candidates),
            "images_selected": len(prepared_inputs.image_paths),
            "extraction_mode": prepared_inputs.extraction_mode,
            "fallback_reason": prepared_inputs.fallback_reason,
            "materialize_ms": prepared_inputs.materialize_ms,
        },
    )
    return prepared_inputs


@asset
def ocr_extraction(
    context: AssetExecutionContext,
    client: AgentClientResource,
    scraped_metadata: RawScrapedData,
    prepared_extraction_inputs: PreparedExtractionInputs,
) -> str:
    """Run multimodal raw extraction from prepared deterministic inputs."""
    api = client.get_client()
    origin_item_id = prepared_extraction_inputs.origin_item_id

    try:
        started = time.perf_counter()
        if prepared_extraction_inputs.fallback_reason:
            context.log.warning(
                "OCR running in text-only mode: %s for item %s",
                prepared_extraction_inputs.fallback_reason,
                origin_item_id,
            )
        llm_started = time.perf_counter()
        raw_text, extraction_metadata = run_raw_extraction_step(
            prepared_inputs=prepared_extraction_inputs,
            scraped_metadata=scraped_metadata,
        )
        llm_ms = round((time.perf_counter() - llm_started) * 1000, 2)

        context.add_output_metadata(
            {
                **extraction_metadata,
                "llm_ms": llm_ms,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "text_preview": MetadataValue.md(
                    (raw_text[:500] + "...") if raw_text else "",
                ),
            },
        )
        return raw_text
    except Exception as e:
        context.log.exception("OCR extraction failed")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise
    else:
        return raw_text
