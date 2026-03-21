"""Thin wrappers around PydanticAI agents used by the extraction stage.

This module is intentionally small:
- it does not load prompt files
- it does not decide retry strategy
- it does not know about Dagster

Callers must pass the prompt explicitly. This keeps the LLM boundary usable from
plain Python, tests, and Dagster assets with the same contract.
"""

from __future__ import annotations

import logging

import requests
from pydantic_ai import Agent, BinaryContent

from .schemas import ProductAnalysisList

logger = logging.getLogger(__name__)

_SUPPORTED_IMAGE_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ),
}


def _get_required_model_id(model_name: str | None) -> str:
    """Return the required explicit model id."""
    model_id = (model_name or "").strip()
    if model_id:
        return model_id
    message = "model_name must be passed explicitly to the agent wrapper"
    raise RuntimeError(message)


def run_raw_extraction(
    *,
    name: str,
    description: str,
    image_urls: list[str],
    prompt: str,
    model_name: str | None = None,
) -> str:
    """Run the raw extraction model with plain image URLs and JSON context."""
    model_id = _get_required_model_id(model_name)
    agent = Agent(model_id)

    user_content: list[str | BinaryContent] = [
        prompt + f"\n\n---\nProduct Name: {name}\nDescription: {description or ''}",
    ]

    loaded_images = 0
    for image_url in image_urls:
        try:
            response = requests.get(image_url, headers=_REQUEST_HEADERS, timeout=30)
            response.raise_for_status()
            file_extension = image_url.rsplit(".", 1)[-1].lower()
            media_type = _SUPPORTED_IMAGE_MEDIA_TYPES.get(file_extension)
            if media_type is None:
                logger.debug("Skipping unsupported image format: %s", file_extension)
                continue

            user_content.append(
                BinaryContent(
                    data=response.content,
                    media_type=media_type,
                ),
            )
            loaded_images += 1
        except (OSError, ValueError) as exc:
            logger.warning(
                "Failed to load image for raw extraction %s: %s",
                image_url,
                exc,
            )

    logger.info(
        "Raw extraction for %s using %s with %s images",
        name,
        model_id,
        loaded_images,
    )

    try:
        result = agent.run_sync(user_content)
    except Exception:
        logger.exception("Raw extraction failed")
        raise
    else:
        return result.output


def run_structured_extraction(
    raw_text: str,
    *,
    prompt: str,
    model_name: str | None = None,
) -> ProductAnalysisList:
    """Run the structured model and return the typed product analysis output."""
    model_id = _get_required_model_id(model_name)

    logger.info("Running structured extraction on %s chars of text", len(raw_text))

    agent = Agent(
        model_id,
        output_type=ProductAnalysisList,
        system_prompt=prompt,
    )

    try:
        result = agent.run_sync(raw_text)
    except Exception:
        logger.exception("Structured extraction failed")
        raise
    else:
        return result.output
