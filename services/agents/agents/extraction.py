"""Non-deterministic extraction helpers used by the agents pipeline.

This module owns the full LLM-facing extraction flow:
- loading prompt templates
- preparing raw extraction input
- parsing context blocks from raw extraction text
- applying simple retry rules for structured analysis

It intentionally works from plain JSON context and image URLs. It does not know
about API platforms, local scraper artifacts, or Dagster resources.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .brain import run_raw_extraction, run_structured_extraction

if TYPE_CHECKING:
    from .acquisition import PreparedExtractionInputs

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CONTEXT_BLOCK_CHAR_LIMIT = 7000
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


def load_raw_extraction_prompt() -> str:
    """Load the base prompt for multimodal raw extraction."""
    return _load_prompt("raw_extraction.md")


def load_structured_extraction_prompt() -> str:
    """Load the base prompt for structured extraction."""
    return _load_prompt("structured_extraction.md")


def run_raw_extraction_step(
    *,
    prepared_inputs: PreparedExtractionInputs,
) -> tuple[str, dict[str, Any]]:
    """Run raw extraction from API-provided JSON context and image URLs."""
    llm_description = build_json_context_block(
        "SCRAPER_CONTEXT",
        prepared_inputs.scraper_context,
    )
    raw_text = run_raw_extraction(
        name=prepared_inputs.page_url,
        description=llm_description,
        image_urls=prepared_inputs.image_urls,
        prompt=load_raw_extraction_prompt(),
    )
    return raw_text, build_raw_extraction_metadata(prepared_inputs=prepared_inputs)


def build_raw_extraction_metadata(
    *,
    prepared_inputs: PreparedExtractionInputs,
) -> dict[str, Any]:
    """Build Dagster metadata for the prepared raw extraction inputs."""
    return {
        "fallback_reason": prepared_inputs.fallback_reason,
        "scraper_context_included": bool(prepared_inputs.scraper_context),
        "images_used": len(prepared_inputs.image_urls),
        "images_sent": prepared_inputs.image_urls,
    }


def run_analysis_pipeline(
    raw_extraction_text: str,
    *,
    extraction_runner: StructuredExtractionRunner = run_structured_extraction,
) -> StructuredAnalysisResult:
    """Run structured analysis and the semantic retry policy for one OCR payload."""
    variant_context = build_variant_extraction_context(raw_extraction_text)
    payload, structured_variant_count = _run_initial_structured_extraction(
        raw_extraction_text,
        extraction_runner=extraction_runner,
    )
    payload, structured_variant_count, reconciliation_retry_used = (
        _apply_reconciliation_retry(
            raw_extraction_text=raw_extraction_text,
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
        raw_extraction_text=raw_extraction_text,
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


def build_variant_extraction_context(
    raw_extraction_text: str,
) -> VariantExtractionContext:
    """Build shared variant expectations from the raw extraction text."""
    expected_variant_signals = extract_expected_variant_signals(raw_extraction_text)
    scraper_context = extract_context_block(raw_extraction_text, "SCRAPER_CONTEXT")
    allowed_variants = extract_allowed_variants_from_scraper_context(scraper_context)
    return VariantExtractionContext(
        expected_variant_count=len(expected_variant_signals),
        allowed_variants=allowed_variants,
    )


def build_json_context_block(title: str, payload: dict | list | None) -> str:
    """Render contextual JSON block for LLM prompts."""
    if not payload:
        return ""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(body) > CONTEXT_BLOCK_CHAR_LIMIT:
        body = f"{body[:CONTEXT_BLOCK_CHAR_LIMIT]}..."
    return f"\n\n[{title}]\n{body}\n[/{title}]"


def extract_context_block(raw_text: str, block_name: str) -> dict | None:
    """Extract JSON payload from contextual block embedded in raw text."""
    pattern = rf"\[{re.escape(block_name)}\]\s*(.*?)\s*\[/{re.escape(block_name)}\]"
    match = re.search(pattern, raw_text, flags=re.DOTALL)
    if not match:
        return None
    block_text = match.group(1).strip()
    if not block_text or block_text.endswith("..."):
        return None
    try:
        payload = json.loads(block_text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_expected_variant_signals(raw_text: str) -> set[str]:
    """Extract flavor and variant hints from OCR text for consistency checks."""
    signals: set[str] = set()
    if not raw_text:
        return signals

    for match in re.findall(r"(?im)^\s*[-*]\s*([^\n]{2,80})\s*$", raw_text):
        line = match.strip(" -:*")
        if not line:
            continue
        lowered = line.lower()
        if lowered in {"not specified in the provided images or text."}:
            continue
        if any(
            token in lowered
            for token in (
                "amendoim",
                "avel",
                "cookies",
                "chocolate",
                "baunilha",
                "morango",
                "coco",
                "frutas",
            )
        ):
            signals.add(line)

    for match in re.findall(r"(?i)referente a\s+([^)\\n]+)", raw_text):
        label = re.sub(r"\s+", " ", match).strip(" .:-")
        if label:
            signals.add(label)

    for match in re.findall(
        r"(?i)\b(?:sabor|flavor|variante|variation)\b[:\s-]+([^\n,;]{2,80})",
        raw_text,
    ):
        label = re.sub(r"\s+", " ", match).strip(" .:-")
        if label:
            signals.add(label)

    return signals


def count_structured_variant_signals(payload: dict) -> int:
    """Count how many variants or flavors structured extraction captured."""
    items = payload.get("items") or []
    variant_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        variant_name = str(item.get("variant_name") or "").strip()
        if variant_name:
            variant_names.add(variant_name.lower())
        for flavor in item.get("flavor_names") or []:
            flavor_name = str(flavor).strip()
            if flavor_name:
                variant_names.add(flavor_name.lower())
    return max(len(items), len(variant_names))


def extract_allowed_variants_from_scraper_context(
    scraper_context: dict | None,
) -> set[str]:
    """Build allowed variant tokens directly from the scraper-context JSON."""
    if not scraper_context:
        return set()
    allowed: set[str] = set()
    _collect_allowed_variant_tokens(scraper_context, allowed, path=())
    return allowed


def count_invalid_variant_tokens(payload: dict, allowed_variants: set[str]) -> int:
    """Count extracted flavor tokens not present in allowed scraper context."""
    if not allowed_variants:
        return 0
    invalid = 0
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        invalid += _count_item_invalid_variant_tokens(item, allowed_variants)
    return invalid


def build_reconciliation_prompt(expected_variants: int) -> str:
    """Prompt forcing strict variant and table reconciliation."""
    return (
        "Convert the raw text into strict structured JSON.\n"
        "Goal: do not miss variants/flavors/nutrition tables.\n"
        f"We detected approximately {expected_variants} variants in the OCR text.\n"
        "Mandatory rules:\n"
        "1) If there is more than one table/flavor, return one item per variant.\n"
        "2) Fill `variant_name`, `flavor_names`, and `is_variant=true` when"
        " applicable.\n"
        "3) Do not collapse different flavors into the same item.\n"
        "4) If a table has no explicit flavor, use a descriptive variant name.\n"
        "5) Keep the schema valid."
    )


def build_context_guard_prompt(allowed_variants: set[str]) -> str:
    """Prompt forcing the model to stay inside the allowed variant set."""
    allowed_list = ", ".join(sorted(allowed_variants))
    return (
        "Convert the raw text to structured JSON while respecting page context.\n"
        "Use only flavors/variants present in the allowed list.\n"
        f"Allowed variants: {allowed_list}\n"
        "If mapping is unclear, keep the item without invented flavors.\n"
        "Keep the schema valid."
    )


def _load_prompt(filename: str) -> str:
    """Load a required prompt template from the prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _run_initial_structured_extraction(
    raw_extraction_text: str,
    *,
    extraction_runner: StructuredExtractionRunner,
) -> tuple[dict, int]:
    """Run the base structured extraction and return payload plus variant count."""
    result = extraction_runner(
        raw_extraction_text,
        prompt=load_structured_extraction_prompt(),
    )
    payload = result.model_dump(by_alias=True)
    return payload, count_structured_variant_signals(payload)


def _apply_reconciliation_retry(
    *,
    raw_extraction_text: str,
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
        raw_extraction_text,
        prompt=build_reconciliation_prompt(expected_variant_count),
    )
    reconciled_payload = reconciled.model_dump(by_alias=True)
    reconciled_variant_count = count_structured_variant_signals(reconciled_payload)
    if reconciled_variant_count >= structured_variant_count:
        return reconciled_payload, reconciled_variant_count, True
    return payload, structured_variant_count, False


def _apply_context_guard_retry(
    *,
    raw_extraction_text: str,
    state: ContextGuardState,
    variant_context: VariantExtractionContext,
    extraction_runner: StructuredExtractionRunner,
) -> tuple[ContextGuardState, bool]:
    """Retry extraction when structured variants drift outside scraper context."""
    if not variant_context.allowed_variants or state.context_invalid_variants <= 0:
        return state, False

    guarded = extraction_runner(
        raw_extraction_text,
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


def _normalize_flavor_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _add_allowed_variant_token(allowed: set[str], value: object) -> None:
    if value is None:
        return
    token = _normalize_flavor_token(str(value))
    if token:
        allowed.add(token)


def _collect_allowed_variant_tokens(
    payload: object,
    allowed: set[str],
    *,
    path: tuple[str, ...],
) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            _collect_allowed_variant_tokens(value, allowed, path=(*path, str(key)))
        return

    if isinstance(payload, list):
        for item in payload:
            _collect_allowed_variant_tokens(item, allowed, path=path)
        return

    if isinstance(payload, str) and _path_looks_variant_related(path):
        _add_allowed_variant_token(allowed, payload)


def _path_looks_variant_related(path: tuple[str, ...]) -> bool:
    lowered_path = tuple(segment.lower() for segment in path)
    current_key = lowered_path[-1] if lowered_path else ""
    if any(
        marker in current_key for marker in ("flavor", "variant", "option", "variation")
    ):
        return True
    if current_key == "values":
        return True
    allowed_leaf_keys = {
        "title",
        "name",
        "complementname",
        "option1",
        "option2",
        "option3",
    }
    if current_key not in allowed_leaf_keys:
        return False
    variant_markers = (
        "variant",
        "variants",
        "option",
        "options",
        "flavor",
        "item",
        "items",
    )
    return any(
        marker in segment for marker in variant_markers for segment in lowered_path[:-1]
    )


def _count_item_invalid_variant_tokens(
    item: dict,
    allowed_variants: set[str],
) -> int:
    return sum(
        1
        for token in _item_variant_tokens(item)
        if _is_invalid_variant_token(token, allowed_variants)
    )


def _item_variant_tokens(item: dict) -> list[str]:
    raw_values: list[str] = []
    variant_name = item.get("variant_name")
    if variant_name:
        raw_values.append(str(variant_name))
    raw_values.extend(str(flavor) for flavor in (item.get("flavor_names") or []))
    return [token for value in raw_values if (token := _normalize_flavor_token(value))]


def _is_invalid_variant_token(token: str, allowed_variants: set[str]) -> bool:
    if token in allowed_variants:
        return False
    return not any(token in allowed or allowed in token for allowed in allowed_variants)
