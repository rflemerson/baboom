"""Dagster asset adapters for the agents pipeline."""

import sys
import time

from pydantic_ai.exceptions import ModelHTTPError

from dagster import AssetExecutionContext, MetadataValue, asset

from ..acquisition import (
    PreparedExtractionInputs,
    build_download_result,
    build_prepared_extraction_inputs,
    get_item_or_raise,
    resolve_source_page_context,
)
from ..client import AgentClient
from ..extraction import (
    build_analysis_input,
    build_analysis_metadata,
    build_image_report_metadata,
    run_analysis_pipeline,
    run_image_report_step,
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
        page = resolve_source_page_context(config, item)
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
def image_report(
    context: AssetExecutionContext,
    prepared_extraction_inputs: PreparedExtractionInputs,
) -> str:
    """Describe all selected images in order before schema extraction."""
    api = AgentClient()
    origin_item_id = prepared_extraction_inputs.origin_item_id

    try:
        started = time.perf_counter()
        if prepared_extraction_inputs.fallback_reason:
            context.log.warning(
                "Image report running without images: %s for item %s",
                prepared_extraction_inputs.fallback_reason,
                origin_item_id,
            )
        llm_started = time.perf_counter()
        report_text, extraction_metadata = run_image_report_step(
            prepared_inputs=prepared_extraction_inputs,
        )
        llm_ms = round((time.perf_counter() - llm_started) * 1000, 2)

        context.add_output_metadata(
            {
                **build_image_report_metadata(
                    prepared_inputs=prepared_extraction_inputs,
                ),
                **extraction_metadata,
                "llm_ms": llm_ms,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "text_preview": MetadataValue.md(
                    (report_text[:500] + "...") if report_text else "",
                ),
            },
        )
    except ModelHTTPError as exc:
        if exc.status_code in {429, 503}:
            context.log.warning("Image report transient provider failure: %s", exc)
        else:
            context.log.exception("Image report failed")
        api.report_error(origin_item_id, str(exc), is_fatal=False)
        raise
    except Exception as exc:
        context.log.exception("Image report failed")
        api.report_error(origin_item_id, str(exc), is_fatal=False)
        raise
    else:
        return report_text


@asset
def product_analysis(
    context: AssetExecutionContext,
    prepared_extraction_inputs: PreparedExtractionInputs,
    image_report: str,
) -> dict:
    """Convert the ordered image report plus JSON context into one product tree."""
    api = AgentClient()
    origin_item_id = prepared_extraction_inputs.origin_item_id

    try:
        started = time.perf_counter()
        analysis_input = build_analysis_input(
            prepared_inputs=prepared_extraction_inputs,
            image_report_text=image_report,
        )
        product = run_analysis_pipeline(analysis_input)

        context.add_output_metadata(
            build_analysis_metadata(
                product=product,
                started=started,
            ),
        )
    except ModelHTTPError as exc:
        if exc.status_code in {429, 503}:
            context.log.warning(
                "Structured analysis transient provider failure: %s",
                exc,
            )
        else:
            context.log.exception("Structured analysis failed")
        api.report_error(origin_item_id, str(exc), is_fatal=False)
        raise
    except Exception as exc:
        context.log.exception("Structured analysis failed")
        api.report_error(origin_item_id, str(exc), is_fatal=False)
        raise
    else:
        return product.model_dump(by_alias=True)


@asset
def extraction_handoff(
    context: AssetExecutionContext,
    product_analysis: dict,
    image_report: str,
    downloaded_assets: dict,
) -> dict:
    """Submit the extracted product tree for backend review."""
    api = AgentClient()
    started = time.perf_counter()
    handoff = build_extraction_handoff(
        product=product_analysis,
        downloaded_assets=downloaded_assets,
        image_report=image_report,
    )
    try:
        submitted = api.submit_extraction(handoff)
        context.add_output_metadata(
            {
                **build_handoff_metadata(
                    handoff=handoff,
                    started=started,
                ),
                "submitted_extraction_id": submitted.get("id"),
            },
        )
    except Exception as exc:
        context.log.exception("Extraction submit failed")
        api.report_error(int(downloaded_assets["origin_item_id"]), str(exc))
        raise
    else:
        return handoff


def build_extraction_handoff(
    *,
    product: dict,
    downloaded_assets: dict,
    image_report: str,
) -> dict:
    """Build the payload submitted to the backend review queue."""
    return {
        "originScrapedItemId": int(downloaded_assets["origin_item_id"]),
        "sourcePageId": downloaded_assets.get("page_id"),
        "sourcePageUrl": downloaded_assets.get("url"),
        "storeSlug": downloaded_assets.get("store_slug"),
        "imageReport": image_report,
        "product": product,
    }


def build_handoff_metadata(
    *,
    handoff: dict,
    started: float,
) -> dict:
    """Build Dagster metadata for the final handoff payload."""
    product = handoff["product"]
    children = product.get("children", [])
    return {
        "origin_item_id": handoff.get("originScrapedItemId"),
        "source_page_id": handoff.get("sourcePageId"),
        "root_product_name": product.get("name", ""),
        "children_detected": len(children),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


ASSET_MODULES = [sys.modules[__name__]]

__all__ = [
    "ASSET_MODULES",
    "build_extraction_handoff",
    "build_handoff_metadata",
    "downloaded_assets",
    "extraction_handoff",
    "image_report",
    "prepared_extraction_inputs",
    "product_analysis",
]
