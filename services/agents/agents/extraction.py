"""Non-deterministic extraction helpers used by the agents pipeline.

The agents service intentionally extracts one product tree per scraped page.
It does not decide catalog identity, variants, or product creation.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .brain import (
    run_image_report_extraction,
    run_structured_extraction,
)

if TYPE_CHECKING:
    from .acquisition import PreparedExtractionInputs
    from .schemas import ExtractedProduct

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CONTEXT_BLOCK_CHAR_LIMIT = 7000


def load_structured_extraction_prompt() -> str:
    """Load the base prompt for structured product-tree extraction."""
    return _load_prompt("structured_extraction.md")


def load_image_ocr_prompt() -> str:
    """Load the base prompt for ordered multi-image OCR-like extraction."""
    return _load_prompt("image_ocr.md")


def run_image_ocr_step(
    *,
    prepared_inputs: PreparedExtractionInputs,
) -> tuple[str, dict[str, Any]]:
    """Extract ordered OCR-like notes for all relevant images in one call."""
    image_manifest_lines = [
        f"- IMAGE_{index}: {image_url}"
        for index, image_url in enumerate(prepared_inputs.image_urls, start=1)
    ]
    description = build_json_context_block(
        "SCRAPER_CONTEXT",
        prepared_inputs.scraper_context,
    )
    if image_manifest_lines:
        description += (
            "\n\n[IMAGE_MANIFEST]\n"
            + "\n".join(image_manifest_lines)
            + "\n[/IMAGE_MANIFEST]"
        )

    ocr_text = run_image_report_extraction(
        name=f"{prepared_inputs.page_url}#ordered-images",
        description=description,
        image_urls=prepared_inputs.image_urls,
        prompt=load_image_ocr_prompt(),
        model_name=_get_configured_model("IMAGE_REPORT_MODEL"),
    )
    return ocr_text, {
        "images_processed": len(prepared_inputs.image_urls),
        "images_sent": prepared_inputs.image_urls,
    }


def build_image_report_metadata(
    *,
    prepared_inputs: PreparedExtractionInputs,
) -> dict[str, Any]:
    """Build Dagster metadata for the prepared image-report inputs."""
    return {
        "fallback_reason": prepared_inputs.fallback_reason,
        "scraper_context_included": bool(prepared_inputs.scraper_context),
        "images_used": len(prepared_inputs.image_urls),
        "images_sent": prepared_inputs.image_urls,
    }


def run_analysis_pipeline(
    analysis_input_text: str,
) -> ExtractedProduct:
    """Run structured extraction once and return the extracted product tree."""
    return run_structured_extraction(
        analysis_input_text,
        prompt=load_structured_extraction_prompt(),
        model_name=_get_configured_model("STRUCTURED_EXTRACTION_MODEL"),
    )


def build_analysis_input(
    *,
    prepared_inputs: PreparedExtractionInputs,
    image_report_text: str,
) -> str:
    """Build the text payload consumed by the schema extraction step."""
    return (
        build_json_context_block(
            "SCRAPER_CONTEXT",
            prepared_inputs.scraper_context,
        )
        + "\n\n[ORDERED_IMAGE_OCR]\n"
        + image_report_text
        + "\n[/ORDERED_IMAGE_OCR]"
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
    is_truncated = len(body) > CONTEXT_BLOCK_CHAR_LIMIT
    if is_truncated:
        body = f"{body[:CONTEXT_BLOCK_CHAR_LIMIT]}..."

    tag = f"{title} (TRUNCATED)" if is_truncated else title
    return f"\n\n[{tag}]\n{body}\n[/{tag}]"


def _load_prompt(filename: str) -> str:
    """Load a required prompt template from the prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _get_configured_model(env_var_name: str) -> str | None:
    """Return the model configured for one extraction stage."""
    return os.getenv(env_var_name) or None
