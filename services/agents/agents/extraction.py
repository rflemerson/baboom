"""Non-deterministic extraction helpers used by the agents pipeline.

The agents service intentionally extracts one product tree per scraped page.
It does not decide catalog identity, variants, or product creation.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .brain import run_raw_extraction, run_structured_extraction
from .schemas import ExtractedProduct

if TYPE_CHECKING:
    from .acquisition import PreparedExtractionInputs

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CONTEXT_BLOCK_CHAR_LIMIT = 7000

StructuredExtractionRunner = Callable[..., ExtractedProduct]


def load_raw_extraction_prompt() -> str:
    """Load the base prompt for multimodal raw extraction."""
    return _load_prompt("raw_extraction.md")


def load_structured_extraction_prompt() -> str:
    """Load the base prompt for structured product-tree extraction."""
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
        model_name=_get_configured_model("RAW_EXTRACTION_MODEL"),
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
) -> ExtractedProduct:
    """Run structured extraction once and return the extracted product tree."""
    return extraction_runner(
        raw_extraction_text,
        prompt=load_structured_extraction_prompt(),
        model_name=_get_configured_model("STRUCTURED_EXTRACTION_MODEL"),
    )


def build_analysis_metadata(
    *,
    product: ExtractedProduct,
    started: float,
) -> dict[str, Any]:
    """Build Dagster metadata for one extracted product tree."""
    return {
        "root_product_name": product.name or "",
        "children_detected": len(product.children),
        "total_product_nodes": count_product_nodes(product),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def count_product_nodes(product: ExtractedProduct) -> int:
    """Count the root product plus all recursive children."""
    return 1 + sum(count_product_nodes(child) for child in product.children)


def build_json_context_block(title: str, payload: dict | list | None) -> str:
    """Render contextual JSON block for LLM prompts."""
    if not payload:
        return ""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(body) > CONTEXT_BLOCK_CHAR_LIMIT:
        body = f"{body[:CONTEXT_BLOCK_CHAR_LIMIT]}..."
    return f"\n\n[{title}]\n{body}\n[/{title}]"


def _load_prompt(filename: str) -> str:
    """Load a required prompt template from the prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _get_configured_model(env_var_name: str) -> str | None:
    """Return the model configured for one extraction stage."""
    return os.getenv(env_var_name) or None
