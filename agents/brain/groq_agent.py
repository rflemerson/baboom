"""Agent for Structured JSON extraction using Groq."""

import logging
import os

from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel

from ..schemas.analysis import ProductAnalysisResult

logger = logging.getLogger(__name__)

# Default model if not specified in flow
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _get_default_prompt():
    """Load the default extraction prompt."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "prompts", "groq_extraction.md"
    )
    if os.path.exists(prompt_path):
        with open(prompt_path) as f:
            return f.read()
    return "Convert the following text to structured JSON."


def get_groq_agent(model_name: str, prompt: str):
    """Factory to create a configured Groq Agent."""
    model = GroqModel(model_name)

    return Agent(
        model,
        output_type=ProductAnalysisResult,
        system_prompt=prompt,
    )


def run_groq_json_extraction(
    raw_text: str, prompt: str | None = None, model_name: str | None = None
) -> ProductAnalysisResult:
    """Runs Groq to convert raw text -> JSON Schema."""
    model_name = model_name or DEFAULT_MODEL
    instructions = prompt or _get_default_prompt()

    logger.info(f"Running Groq ({model_name}) on {len(raw_text)} chars of text...")

    agent = get_groq_agent(model_name, instructions)

    try:
        result = agent.run_sync(raw_text)
        return result.output
    except Exception as e:
        logger.error(f"Groq output extraction failed: {e}")
        raise
