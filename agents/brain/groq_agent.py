import logging
import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from ..schemas.analysis import ProductAnalysisResult

logger = logging.getLogger(__name__)

# Cerebras Llama 70B
DEFAULT_MODEL = "llama-3.3-70b"


def _get_default_prompt():
    """Load the default extraction prompt."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "prompts", "groq_extraction.md"
    )
    if os.path.exists(prompt_path):
        with open(prompt_path) as f:
            return f.read()
    return "Convert the following text to structured JSON."


def get_agent(model_name: str, prompt: str):
    """Factory to create a configured Agent (Cerebras via OpenAI compatibility)."""
    # Requires OPENAI_BASE_URL and OPENAI_API_KEY environment variables to be set for Cerebras
    model = OpenAIModel(model_name)

    return Agent(
        model,
        output_type=ProductAnalysisResult,
        system_prompt=prompt,
    )


def run_groq_json_extraction(
    raw_text: str, prompt: str | None = None, model_name: str | None = None
) -> ProductAnalysisResult:
    """Runs AI to convert raw text -> JSON Schema (Cerebras)."""
    model_name = model_name or DEFAULT_MODEL
    instructions = prompt or _get_default_prompt()

    logger.info(f"Running Agent ({model_name}) on {len(raw_text)} chars of text...")

    agent = get_agent(model_name, instructions)

    try:
        result = agent.run_sync(raw_text)
        return result.output
    except Exception as e:
        logger.error(f"Structured extraction failed (Model: {model_name}): {e}")
        raise
