"""Dagster asset: transform OCR raw text into structured product analysis JSON."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from dagster import AssetExecutionContext, asset

from ...brain.analysis_pipeline import (
    MIN_EXPECTED_VARIANTS_FOR_RECONCILIATION,
    build_analysis_metadata,
    run_analysis_pipeline,
)
from ...brain.structured_agent import run_structured_extraction

if TYPE_CHECKING:
    from ..resources import AgentClientResource
    from .shared import ItemConfig


@asset
def product_analysis(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    ocr_extraction: str,
) -> dict:
    """Convert raw text into a structured list of product analyses."""
    api = client.get_client()
    try:
        started = time.perf_counter()
        analysis = run_analysis_pipeline(
            ocr_extraction,
            extraction_runner=run_structured_extraction,
        )

        if (
            analysis.variant_context.expected_variant_count
            >= MIN_EXPECTED_VARIANTS_FOR_RECONCILIATION
            and analysis.reconciliation_retry_used
        ):
            context.log.warning(
                "Structured extraction under-detected variants (%s/%s). "
                "Reconciliation prompt improved the result.",
                analysis.structured_variant_count,
                analysis.variant_context.expected_variant_count,
            )
        if analysis.context_guard_retry_used:
            context.log.warning(
                "Structured extraction returned variants outside %s (%s invalid). "
                "Context guard improved the result.",
                "catalog/scraper context",
                analysis.context_invalid_variants,
            )

        context.add_output_metadata(
            build_analysis_metadata(
                analysis=analysis,
                started=(time.perf_counter() - started) * 1000,
            ),
        )
    except Exception as exc:
        context.log.exception("Structured analysis failed")
        api.report_error(config.item_id, str(exc), is_fatal=False)
        raise
    else:
        return analysis.payload
