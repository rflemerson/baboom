"""Dagster asset: run OCR/raw multimodal extraction using selected page images."""

import json
import time

from dagster import AssetExecutionContext, MetadataValue, asset

from ...brain.raw_extraction_agent import run_raw_extraction
from ...schemas.product import RawScrapedData
from ..resources import AgentClientResource, ScraperServiceResource, StorageResource
from .shared import (
    _build_image_sequence_context,
    _build_json_context_block,
    _select_images_for_ocr,
)


@asset
def ocr_extraction(
    context: AssetExecutionContext,
    scraper: ScraperServiceResource,
    storage: StorageResource,
    client: AgentClientResource,
    scraped_metadata: RawScrapedData,
    downloaded_assets: dict,
) -> str:
    """Runs multimodal raw extraction over top-ranked page images."""
    store = storage.get_storage()
    service = scraper.get_service()
    api = client.get_client()
    origin_item_id = int(downloaded_assets["origin_item_id"])
    page_url = downloaded_assets["url"]

    bucket, _ = downloaded_assets["storage_path"].split("/", 1)
    try:
        started = time.perf_counter()
        candidates: list[dict] = []
        image_paths: list[str] = []
        candidates_key = "candidates.json"
        site_data: dict | None = None
        scraper_context: dict | None = None
        raw_scraper_context = downloaded_assets.get("source_page_raw_content")
        scraper_context_type = str(
            downloaded_assets.get("source_page_content_type") or ""
        ).upper()

        if raw_scraper_context and scraper_context_type == "JSON":
            try:
                parsed_context = json.loads(raw_scraper_context)
                if isinstance(parsed_context, dict):
                    scraper_context = parsed_context
            except Exception:
                scraper_context = None

        if store.exists(bucket, "site_data.json"):
            site_data = json.loads(store.download(bucket, "site_data.json"))

        materialize_ms = 0.0
        if not store.exists(bucket, candidates_key):
            materialize_started = time.perf_counter()
            candidates = service.materialize_candidates(bucket, page_url)
            materialize_ms = round(
                (time.perf_counter() - materialize_started) * 1000, 2
            )
        if not candidates and store.exists(bucket, candidates_key):
            candidates = json.loads(store.download(bucket, candidates_key))
        if candidates:
            image_paths = _select_images_for_ocr(
                candidates,
                bucket,
                product_name=scraped_metadata.name or "",
                page_url=page_url,
            )
        extraction_mode = "multimodal"
        fallback_reason = ""
        if not image_paths:
            extraction_mode = "text_only"
            fallback_reason = (
                "no_candidates_available" if not candidates else "selection_empty"
            )
            context.log.warning(
                "OCR running in text-only mode: "
                f"{fallback_reason} for item {origin_item_id}"
            )
        sequence_context = _build_image_sequence_context(candidates, image_paths)
        llm_description = (
            (scraped_metadata.description or "")
            + sequence_context
            + _build_json_context_block("SITE_DATA", site_data)
            + _build_json_context_block("SCRAPER_CONTEXT", scraper_context)
        )

        llm_started = time.perf_counter()
        raw_text = run_raw_extraction(
            name=scraped_metadata.name or page_url,
            description=llm_description,
            image_paths=image_paths,
        )
        llm_ms = round((time.perf_counter() - llm_started) * 1000, 2)

        context.add_output_metadata(
            {
                "extraction_mode": extraction_mode,
                "fallback_reason": fallback_reason,
                "candidates_available": len(candidates),
                "scraper_context_included": bool(scraper_context),
                "images_used": len(image_paths),
                "images_sent": image_paths,
                "materialize_ms": materialize_ms,
                "llm_ms": llm_ms,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "text_preview": MetadataValue.md(
                    (raw_text[:500] + "...") if raw_text else ""
                ),
            }
        )
        return raw_text
    except Exception as e:
        context.log.error(f"OCR extraction failed: {e}")
        api.report_error(origin_item_id, str(e), is_fatal=False)
        raise
