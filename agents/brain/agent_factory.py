import logging
import os

from pydantic_ai.models import Model
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel

logger = logging.getLogger(__name__)


def get_model(model_id: str | None = None) -> Model | str:
    """Build a pydantic-ai model from `provider:model_name`."""
    # Use environment variable if no model_id provided
    env_model = os.getenv("LLM_MODEL")
    model_id = model_id or env_model or "groq:llama-3.3-70b-versatile"

    if not model_id:
        model_id = "groq:llama-3.3-70b-versatile"

    provider = "groq"
    model_name = model_id

    if ":" in model_id:
        provider, model_name = model_id.split(":", 1)
    else:
        # If no colon, assume it's just the model name for the default provider
        logger.info(f"No provider prefix in '{model_id}', assuming 'groq'")

    logger.info(f"Instantiating model provider='{provider}' model='{model_name}'")

    if provider == "groq":
        return GroqModel(model_name)

    if provider == "openai":
        return OpenAIModel(model_name)

    if provider in {"google-gla", "gemini"}:
        return GeminiModel(model_name)

    # Default fallback to string-based model name (pydantic-ai might handle it)
    return model_name
