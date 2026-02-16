"""Dagster asset: transform OCR raw text into structured product analysis JSON."""

import time

from dagster import AssetExecutionContext, asset

from ...brain.structured_agent import run_structured_extraction
from ..resources import AgentClientResource
from .shared import (
    ItemConfig,
    _build_context_guard_prompt,
    _build_reconciliation_prompt,
    _count_invalid_variant_tokens,
    _count_structured_variant_signals,
    _extract_allowed_variants_from_scraper_context,
    _extract_context_block,
    _extract_expected_variant_signals,
)


@asset
def product_analysis(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    ocr_extraction: str,
) -> dict:
    """Converts raw text into structured list of product analyses."""
    api = client.get_client()
    try:
        started = time.perf_counter()
        result = run_structured_extraction(ocr_extraction)
        payload = result.model_dump(by_alias=True)

        expected_variant_signals = _extract_expected_variant_signals(ocr_extraction)
        expected_variant_count = len(expected_variant_signals)
        structured_variant_count = _count_structured_variant_signals(payload)
        reconciliation_retry_used = False
        context_guard_retry_used = False
        context_invalid_variants = 0

        if (
            expected_variant_count >= 2
            and structured_variant_count < expected_variant_count
        ):
            context.log.warning(
                "Structured extraction under-detected variants "
                f"({structured_variant_count}/{expected_variant_count}). Retrying with reconciliation prompt."
            )
            reconciled = run_structured_extraction(
                ocr_extraction,
                prompt=_build_reconciliation_prompt(expected_variant_count),
            )
            reconciled_payload = reconciled.model_dump(by_alias=True)
            reconciled_variant_count = _count_structured_variant_signals(
                reconciled_payload
            )
            if reconciled_variant_count >= structured_variant_count:
                payload = reconciled_payload
                structured_variant_count = reconciled_variant_count
                reconciliation_retry_used = True

        scraper_context = _extract_context_block(ocr_extraction, "SCRAPER_CONTEXT")
        allowed_variants = _extract_allowed_variants_from_scraper_context(
            scraper_context
        )
        context_invalid_variants = _count_invalid_variant_tokens(
            payload, allowed_variants
        )
        if allowed_variants and context_invalid_variants > 0:
            source_label = "catalog/scraper context"
            context.log.warning(
                "Structured extraction returned variants outside "
                f"{source_label} ({context_invalid_variants} invalid). Retrying with context guard."
            )
            guarded = run_structured_extraction(
                ocr_extraction,
                prompt=_build_context_guard_prompt(allowed_variants),
            )
            guarded_payload = guarded.model_dump(by_alias=True)
            guarded_invalid = _count_invalid_variant_tokens(
                guarded_payload, allowed_variants
            )
            guarded_variant_count = _count_structured_variant_signals(guarded_payload)
            if guarded_invalid < context_invalid_variants or (
                guarded_invalid == context_invalid_variants
                and guarded_variant_count >= structured_variant_count
            ):
                payload = guarded_payload
                structured_variant_count = guarded_variant_count
                context_invalid_variants = guarded_invalid
                context_guard_retry_used = True

        context.add_output_metadata(
            {
                "items_detected": len(payload.get("items", [])),
                "variants_detected_raw": expected_variant_count,
                "variants_detected_structured": structured_variant_count,
                "reconciliation_retry_used": reconciliation_retry_used,
                "context_guard_retry_used": context_guard_retry_used,
                "context_invalid_variants": context_invalid_variants,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        return payload
    except Exception as e:
        context.log.error(f"Structured analysis failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise
