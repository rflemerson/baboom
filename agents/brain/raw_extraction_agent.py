import logging
import os

from pydantic_ai import Agent, BinaryContent

logger = logging.getLogger(__name__)

# Default model if not specified in flow
DEFAULT_MODEL = "google-gla:gemma-3-27b-it"


def _get_default_prompt():
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "prompts", "raw_extraction.md"
    )
    if os.path.exists(prompt_path):
        with open(prompt_path) as f:
            return f.read()
    return "Extract product data from images and text."


def run_raw_extraction(
    name: str,
    description: str,
    image_paths: list[str],
    prompt: str | None = None,
    model_name: str | None = None,
) -> str:
    """Runs a multimodal agent (default Gemma 3) to extract raw text data."""
    from ..storage import get_storage  # noqa: PLC0415

    storage = get_storage()
    model_name = model_name or DEFAULT_MODEL
    instructions = prompt or _get_default_prompt()

    agent = Agent(model_name)

    user_content: list[str | BinaryContent] = [
        instructions
        + f"\n\n---\nProduct Name: {name}\nDescription: {description or ''}"
    ]

    # Load Images
    loaded_images = 0
    for path in image_paths:
        try:
            bucket, key = path.split("/", 1)
            if storage.exists(bucket, key):
                img_data = storage.download(bucket, key)
                user_content.append(
                    BinaryContent(data=img_data, media_type="image/jpeg")
                )
                loaded_images += 1
        except Exception as e:
            logger.warning(f"Failed to load image for raw extraction {path}: {e}")

    logger.info(
        f"Raw Extraction: {name} | Model: {model_name} | Images: {loaded_images}"
    )

    try:
        result = agent.run_sync(user_content)
        if hasattr(result, "data"):
            return result.data
        if hasattr(result, "output"):
            return result.output
        return str(result)
    except Exception as e:
        logger.error(f"Raw extraction failed: {e}")
        return f"ERROR: {e!s}"
