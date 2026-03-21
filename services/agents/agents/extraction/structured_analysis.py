"""Pure structured-analysis pipeline helpers for non-deterministic extraction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..brain.structured_agent import run_structured_extraction
from .context_utils import (
    build_context_guard_prompt,
    build_reconciliation_prompt,
    count_invalid_variant_tokens,
    count_structured_variant_signals,
    extract_allowed_variants_from_scraper_context,
    extract_context_block,
    extract_expected_variant_signals,
)

MIN_EXPECTED_VARIANTS_FOR_RECONCILIATION = 2

StructuredExtractionRunner = Callable[..., object]


@dataclass(frozen=True, slots=True)
class VariantExtractionContext:
    """Variant-related context derived from OCR extraction text."""

    expected_variant_count: int
    allowed_variants: set[str]


@dataclass(frozen=True, slots=True)
class StructuredAnalysisResult:
    """Final structured payload plus metadata about retry decisions."""

    payload: dict
    variant_context: VariantExtractionContext
    structured_variant_count: int
    reconciliation_retry_used: bool
    context_guard_retry_used: bool
    context_invalid_variants: int


@dataclass(frozen=True, slots=True)
class ContextGuardState:
    """Current payload state used when evaluating the context-guard retry."""

    payload: dict
    structured_variant_count: int
    context_invalid_variants: int


def build_variant_extraction_context(ocr_extraction: str) -> VariantExtractionContext:
    """Build shared variant expectations from the OCR extraction text."""
    expected_variant_signals = extract_expected_variant_signals(ocr_extraction)
    scraper_context = extract_context_block(ocr_extraction, "SCRAPER_CONTEXT")
    allowed_variants = extract_allowed_variants_from_scraper_context(scraper_context)
    return VariantExtractionContext(
        expected_variant_count=len(expected_variant_signals),
        allowed_variants=allowed_variants,
    )


def build_analysis_metadata(
    *,
    analysis: StructuredAnalysisResult,
    started: float,
) -> dict[str, Any]:
    """Build Dagster metadata for one structured analysis result."""
    return {
        "items_detected": len(analysis.payload.get("items", [])),
        "variants_detected_raw": analysis.variant_context.expected_variant_count,
        "variants_detected_structured": analysis.structured_variant_count,
        "reconciliation_retry_used": analysis.reconciliation_retry_used,
        "context_guard_retry_used": analysis.context_guard_retry_used,
        "context_invalid_variants": analysis.context_invalid_variants,
        "duration_ms": round(started, 2),
    }


def run_analysis_pipeline(
    ocr_extraction: str,
    *,
    extraction_runner: StructuredExtractionRunner = run_structured_extraction,
) -> StructuredAnalysisResult:
    """Run structured analysis and the semantic retry policy for one OCR payload."""
    variant_context = build_variant_extraction_context(ocr_extraction)
    payload, structured_variant_count = _run_initial_structured_extraction(
        ocr_extraction,
        extraction_runner=extraction_runner,
    )
    payload, structured_variant_count, reconciliation_retry_used = (
        _apply_reconciliation_retry(
            ocr_extraction=ocr_extraction,
            payload=payload,
            structured_variant_count=structured_variant_count,
            expected_variant_count=variant_context.expected_variant_count,
            extraction_runner=extraction_runner,
        )
    )
    context_invalid_variants = count_invalid_variant_tokens(
        payload,
        variant_context.allowed_variants,
    )
    context_guard_state, context_guard_retry_used = _apply_context_guard_retry(
        ocr_extraction=ocr_extraction,
        state=ContextGuardState(
            payload=payload,
            structured_variant_count=structured_variant_count,
            context_invalid_variants=context_invalid_variants,
        ),
        variant_context=variant_context,
        extraction_runner=extraction_runner,
    )
    return StructuredAnalysisResult(
        payload=context_guard_state.payload,
        variant_context=variant_context,
        structured_variant_count=context_guard_state.structured_variant_count,
        reconciliation_retry_used=reconciliation_retry_used,
        context_guard_retry_used=context_guard_retry_used,
        context_invalid_variants=context_guard_state.context_invalid_variants,
    )


def _run_initial_structured_extraction(
    ocr_extraction: str,
    *,
    extraction_runner: StructuredExtractionRunner,
) -> tuple[dict, int]:
    """Run the base structured extraction and return payload plus variant count."""
    result = extraction_runner(ocr_extraction)
    payload = result.model_dump(by_alias=True)
    return payload, count_structured_variant_signals(payload)


def _apply_reconciliation_retry(
    *,
    ocr_extraction: str,
    payload: dict,
    structured_variant_count: int,
    expected_variant_count: int,
    extraction_runner: StructuredExtractionRunner,
) -> tuple[dict, int, bool]:
    """Retry extraction when OCR suggests more variants than the payload captured."""
    if (
        expected_variant_count < MIN_EXPECTED_VARIANTS_FOR_RECONCILIATION
        or structured_variant_count >= expected_variant_count
    ):
        return payload, structured_variant_count, False

    reconciled = extraction_runner(
        ocr_extraction,
        prompt=build_reconciliation_prompt(expected_variant_count),
    )
    reconciled_payload = reconciled.model_dump(by_alias=True)
    reconciled_variant_count = count_structured_variant_signals(reconciled_payload)
    if reconciled_variant_count >= structured_variant_count:
        return reconciled_payload, reconciled_variant_count, True
    return payload, structured_variant_count, False


def _apply_context_guard_retry(
    *,
    ocr_extraction: str,
    state: ContextGuardState,
    variant_context: VariantExtractionContext,
    extraction_runner: StructuredExtractionRunner,
) -> tuple[ContextGuardState, bool]:
    """Retry extraction when structured variants drift outside scraper context."""
    if not variant_context.allowed_variants or state.context_invalid_variants <= 0:
        return state, False

    guarded = extraction_runner(
        ocr_extraction,
        prompt=build_context_guard_prompt(variant_context.allowed_variants),
    )
    guarded_payload = guarded.model_dump(by_alias=True)
    guarded_invalid = count_invalid_variant_tokens(
        guarded_payload,
        variant_context.allowed_variants,
    )
    guarded_variant_count = count_structured_variant_signals(guarded_payload)
    if guarded_invalid < state.context_invalid_variants or (
        guarded_invalid == state.context_invalid_variants
        and guarded_variant_count >= state.structured_variant_count
    ):
        return (
            ContextGuardState(
                payload=guarded_payload,
                structured_variant_count=guarded_variant_count,
                context_invalid_variants=guarded_invalid,
            ),
            True,
        )
    return state, False
