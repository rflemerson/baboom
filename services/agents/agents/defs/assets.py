"""Dagster asset adapters for the agents pipeline."""

import time

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
    build_analysis_metadata,
    run_analysis_pipeline,
    run_raw_extraction_step,
)
from . import pipeline as pipeline_module

ItemConfig = pipeline_module.ItemConfig


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
                "has_api_context": bool(page.source_page_api_context),
                "has_html_structured_data": bool(page.source_page_html_structured_data),
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
    """Convert raw text into one extracted product tree."""
    api = AgentClient()
    try:
        started = time.perf_counter()
        product = run_analysis_pipeline(
            raw_extraction,
            extraction_runner=run_structured_extraction,
        )

        context.add_output_metadata(
            build_analysis_metadata(
                product=product,
                started=started,
            ),
        )
    except Exception as exc:
        context.log.exception("Structured analysis failed")
        api.report_error(config.item_id, str(exc), is_fatal=False)
        raise
    else:
        return product.model_dump(by_alias=True)


@asset
def extraction_handoff(
    context: AssetExecutionContext,
    config: ItemConfig,
    product_analysis: dict,
    raw_extraction: str,
    downloaded_assets: dict,
) -> dict:
    """Emit the extracted product tree without creating catalog records."""
    _ = config
    started = time.perf_counter()
    handoff = build_extraction_handoff(
        product=product_analysis,
        downloaded_assets=downloaded_assets,
        raw_extraction=raw_extraction,
    )
    context.add_output_metadata(
        build_handoff_metadata(
            handoff=handoff,
            started=started,
        ),
    )
    return handoff


def build_extraction_handoff(
    *,
    product: dict,
    downloaded_assets: dict,
    raw_extraction: str,
) -> dict:
    """Build the final payload emitted by the Dagster pipeline."""
    return {
        "originScrapedItemId": int(downloaded_assets["origin_item_id"]),
        "sourcePageId": downloaded_assets.get("page_id"),
        "sourcePageUrl": downloaded_assets.get("url"),
        "storeSlug": downloaded_assets.get("store_slug"),
        "rawExtraction": raw_extraction,
        "product": product,
    }


def build_handoff_metadata(
    *,
    handoff: dict,
    started: float,
) -> dict:
    """Build Dagster metadata for the final handoff payload."""
    product = handoff.get("product") if isinstance(handoff, dict) else {}
    children = product.get("children") if isinstance(product, dict) else []
    return {
        "origin_item_id": handoff.get("originScrapedItemId"),
        "source_page_id": handoff.get("sourcePageId"),
        "root_product_name": product.get("name") if isinstance(product, dict) else "",
        "children_detected": len(children) if isinstance(children, list) else 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


ASSET_MODULES = [__import__(__name__, fromlist=["*"])]

__all__ = [
    "ASSET_MODULES",
    "build_extraction_handoff",
    "build_handoff_metadata",
    "downloaded_assets",
    "extraction_handoff",
    "prepared_extraction_inputs",
    "product_analysis",
    "raw_extraction",
]
