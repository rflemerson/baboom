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
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
from pydantic_ai import Agent, BinaryContent

from .schemas import ExtractedProduct

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


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    """Image bytes prepared for the multimodal model."""

    url: str
    data: bytes
    media_type: str


def _get_required_model_id(model_name: str | None) -> str:
    """Return the required explicit model id."""
    model_id = (model_name or "").strip()
    if model_id:
        return model_id
    message = "model_name must be passed explicitly to the agent wrapper"
    raise RuntimeError(message)


def run_image_report_extraction(
    *,
    run_label: str,
    description: str,
    image_urls: list[str],
    prompt: str,
    model_name: str | None = None,
) -> str:
    """Run the multimodal image-report model with image URLs and JSON context."""
    model_id = _get_required_model_id(model_name)
    agent = Agent(model_id)
    downloaded_images = _download_images(image_urls)
    user_content = _build_multimodal_user_content(
        prompt=prompt,
        description=description,
        downloaded_images=downloaded_images,
    )

    logger.info(
        "Image report extraction for %s using %s with %s images",
        run_label,
        model_id,
        len(downloaded_images),
    )

    try:
        result = agent.run_sync(user_content)
    except Exception:
        logger.exception("Image report extraction failed")
        raise
    else:
        return result.output


def run_structured_extraction(
    analysis_input_text: str,
    *,
    prompt: str,
    model_name: str | None = None,
) -> ExtractedProduct:
    """Run the structured model and return one extracted product tree."""
    model_id = _get_required_model_id(model_name)

    logger.info(
        "Running structured extraction on %s chars of text",
        len(analysis_input_text),
    )

    agent = Agent(
        model_id,
        output_type=ExtractedProduct,
        system_prompt=prompt,
    )

    try:
        result = agent.run_sync(analysis_input_text)
    except Exception:
        logger.exception("Structured extraction failed")
        raise
    else:
        return result.output


def _build_multimodal_user_content(
    *,
    prompt: str,
    description: str,
    downloaded_images: list[DownloadedImage],
) -> list[str | BinaryContent]:
    """Build the multimodal model payload from already downloaded images."""
    user_content: list[str | BinaryContent] = [
        prompt + f"\n\n---\n{description or ''}",
    ]
    user_content.extend(
        BinaryContent(
            data=image.data,
            media_type=image.media_type,
        )
        for image in downloaded_images
    )

    return user_content


def _download_images(image_urls: list[str]) -> list[DownloadedImage]:
    """Download supported images, skipping individual failures explicitly."""
    downloaded_images: list[DownloadedImage] = []
    for image_url in image_urls:
        downloaded_image = _download_image(image_url)
        if downloaded_image is not None:
            downloaded_images.append(downloaded_image)
    return downloaded_images


def _download_image(image_url: str) -> DownloadedImage | None:
    """Download one supported image URL for multimodal input."""
    media_type = _resolve_image_media_type(image_url)
    if media_type is None:
        logger.debug("Skipping unsupported image format: %s", image_url)
        return None

    try:
        response = requests.get(image_url, headers=_REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except (OSError, ValueError, requests.RequestException) as exc:
        logger.warning(
            "Failed to load image for multimodal extraction %s: %s",
            image_url,
            exc,
        )
        return None

    return DownloadedImage(
        url=image_url,
        data=response.content,
        media_type=media_type,
    )


def _resolve_image_media_type(image_url: str) -> str | None:
    """Resolve supported image media type from URL path, ignoring querystrings."""
    path = urlsplit(image_url).path
    file_extension = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _SUPPORTED_IMAGE_MEDIA_TYPES.get(file_extension)
