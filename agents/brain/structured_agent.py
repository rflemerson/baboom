import logging
import os

from pydantic_ai import Agent

from ..schemas.analysis import ProductAnalysisList
from .agent_factory import get_model

logger = logging.getLogger(__name__)


def _get_default_prompt():
    """Load the default extraction prompt."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "prompts",
        "structured_extraction.md",
    )
    if os.path.exists(prompt_path):
        with open(prompt_path) as f:
            return f.read()
    return "Convert the following text to structured JSON."


def get_agent(model_name: str | None, prompt: str):
    """Factory to create a configured Agent (Generic)."""
    model = get_model(model_name)

    return Agent(
        model,
        output_type=ProductAnalysisList,
        system_prompt=prompt,
    )


def run_structured_extraction(
    raw_text: str, prompt: str | None = None, model_name: str | None = None
) -> ProductAnalysisList:
    """Runs AI to convert raw text -> JSON Schema (Generic)."""
    instructions = prompt or _get_default_prompt()

    logger.info(f"Running Structured Extraction on {len(raw_text)} chars of text...")

    agent = get_agent(model_name, instructions)

    try:
        result = agent.run_sync(raw_text)
        return result.output
    except Exception as e:
        logger.error(f"Structured extraction failed: {e}")
        raise
