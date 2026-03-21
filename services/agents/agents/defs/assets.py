"""Dagster asset adapters for the agents pipeline."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from dagster import AssetExecutionContext, MetadataValue, asset

from ..acquisition import (
    PreparedExtractionInputs,
    build_download_result,
    build_prepared_extraction_inputs,
    get_item_or_raise,
    resolve_source_page_context,
)
from ..brain import run_structured_extraction
from ..client import AgentClient
from ..extraction import (
    MIN_EXPECTED_VARIANTS_FOR_RECONCILIATION,
    build_analysis_metadata,
    run_analysis_pipeline,
    run_raw_extraction_step,
)
from ..publishing import (
    build_publish_origin_context,
    build_upload_metadata,
    publish_analysis_item,
    resolve_analysis_items,
)

if TYPE_CHECKING:
    from .pipeline import ItemConfig


@asset
def downloaded_assets(
    context: AssetExecutionContext,
    config: ItemConfig,
) -> dict:
    """Normalize API source-page context for downstream deterministic stages."""
    api = AgentClient()

    try:
        started = time.perf_counter()
        item = get_item_or_raise(api, config.item_id)
        page = resolve_source_page_context(api, config, item)
        context.add_output_metadata(
            {
                "url": MetadataValue.url(page.page_url),
                "page_id": page.page_id,
                "origin_item_id": page.item_id,
                "scraper_context_type": page.source_page_content_type or "unknown",
                "has_scraper_context": bool(page.source_page_raw_content),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
    except Exception as exc:
        context.log.exception("Download failed")
        api.report_error(config.item_id, str(exc), is_fatal=False)
        raise
    else:
        return build_download_result(page)


@asset
def prepared_extraction_inputs(
    context: AssetExecutionContext,
    downloaded_assets: dict,
) -> PreparedExtractionInputs:
    """Prepare deterministic extraction inputs from API scraper context."""
    prepared_inputs = build_prepared_extraction_inputs(
        downloaded_assets=downloaded_assets,
    )
    context.add_output_metadata(
        {
            "page_url": MetadataValue.url(prepared_inputs.page_url),
            "images_selected": len(prepared_inputs.image_urls),
            "fallback_reason": prepared_inputs.fallback_reason,
        },
    )
    return prepared_inputs


@asset
def raw_extraction(
    context: AssetExecutionContext,
    prepared_extraction_inputs: PreparedExtractionInputs,
) -> str:
    """Run raw extraction directly from API-provided images and JSON context."""
    api = AgentClient()
    origin_item_id = prepared_extraction_inputs.origin_item_id

    try:
        started = time.perf_counter()
        if prepared_extraction_inputs.fallback_reason:
            context.log.warning(
                "Raw extraction running without images: %s for item %s",
                prepared_extraction_inputs.fallback_reason,
                origin_item_id,
            )
        llm_started = time.perf_counter()
        raw_text, extraction_metadata = run_raw_extraction_step(
            prepared_inputs=prepared_extraction_inputs,
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
    except Exception as exc:
        context.log.exception("Raw extraction failed")
        api.report_error(origin_item_id, str(exc), is_fatal=False)
        raise
    else:
        return raw_text


@asset
def product_analysis(
    context: AssetExecutionContext,
    config: ItemConfig,
    raw_extraction: str,
) -> dict:
    """Convert raw text into a structured list of product analyses."""
    api = AgentClient()
    try:
        started = time.perf_counter()
        analysis = run_analysis_pipeline(
            raw_extraction,
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


@asset
def upload_to_api(
    context: AssetExecutionContext,
    config: ItemConfig,
    product_analysis: dict,
    _downloaded_assets: dict,
) -> list[dict]:
    """Create one product per analyzed item and link generated scraped items."""
    api = AgentClient()
    try:
        started = time.perf_counter()
        origin_context = build_publish_origin_context(
            api,
            item_id=config.item_id,
            url=config.url,
            store_slug=config.store_slug,
        )
        items = resolve_analysis_items(
            product_analysis,
            origin_context.item,
        )

        results: list[dict] = []
        created_count = 0
        for idx, analysis_data in enumerate(items):
            item_result = publish_analysis_item(
                context=context,
                api=api,
                idx=idx,
                analysis_data=analysis_data,
                origin=origin_context,
            )
            if item_result.variant_created:
                created_count += 1
            results.append(item_result.result)

        context.add_output_metadata(
            build_upload_metadata(
                results=results,
                created_count=created_count,
                page_id=origin_context.page_id,
                started=started,
            ),
        )
    except Exception as exc:
        context.log.exception("Upload failed")
        api.report_error(config.item_id, str(exc), is_fatal=False)
        raise
    else:
        return results


ASSET_MODULES = [__import__(__name__, fromlist=["*"])]

__all__ = [
    "ASSET_MODULES",
    "downloaded_assets",
    "prepared_extraction_inputs",
    "product_analysis",
    "raw_extraction",
    "upload_to_api",
]
