"""Model factory for creating provider-backed pydantic-ai model instances."""

import logging
import os
from collections.abc import Callable

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.google import GoogleProvider

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "groq"
DEFAULT_MODEL_NAME = "llama-3.3-70b-versatile"

ProviderBuilder = Callable[[str], Model]

_PROVIDER_ALIASES = {
    "groq": "groq",
    "openai": "openai",
    "gemini": "google-gla",
    "google-gla": "google-gla",
    "google": "google-gla",
}

_MODEL_BUILDERS: dict[str, ProviderBuilder] = {
    "groq": lambda model_name: GroqModel(model_name),
    "openai": lambda model_name: OpenAIModel(model_name),
    "google-gla": lambda model_name: GoogleModel(
        model_name,
        provider=GoogleProvider(
            api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            vertexai=False,
        ),
    ),
}


def _parse_model_id(model_id: str) -> tuple[str, str]:
    """Parse provider/model while applying aliases and defaults."""
    provider = DEFAULT_PROVIDER
    model_name = model_id

    if ":" in model_id:
        raw_provider, raw_model_name = model_id.split(":", 1)
        normalized_provider = raw_provider.strip().lower() or DEFAULT_PROVIDER
        provider = _PROVIDER_ALIASES.get(normalized_provider, normalized_provider)
        model_name = raw_model_name.strip() or DEFAULT_MODEL_NAME
    else:
        logger.info(
            "No provider prefix in '%s', assuming '%s'", model_id, DEFAULT_PROVIDER
        )
        model_name = model_name.strip() or DEFAULT_MODEL_NAME

    return provider, model_name


def get_model(model_id: str | None = None) -> Model | str:
    """Build a pydantic-ai model from `provider:model_name`."""
    env_model = os.getenv("LLM_MODEL", "").strip()
    resolved_model_id = (
        model_id or env_model or f"{DEFAULT_PROVIDER}:{DEFAULT_MODEL_NAME}"
    ).strip() or f"{DEFAULT_PROVIDER}:{DEFAULT_MODEL_NAME}"
    provider, model_name = _parse_model_id(resolved_model_id)

    logger.info(f"Instantiating model provider='{provider}' model='{model_name}'")

    builder = _MODEL_BUILDERS.get(provider)
    if builder is not None:
        return builder(model_name)

    # Default fallback to string-based model name (pydantic-ai might handle it)
    logger.warning("Unknown provider '%s'. Falling back to raw model name.", provider)
    return model_name or resolved_model_id
