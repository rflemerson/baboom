import logging
import os

from dotenv import load_dotenv
from pydantic_ai import Agent

from ..schemas.metadata import ProductMetadata

load_dotenv()
logger = logging.getLogger(__name__)

model_name = os.getenv("LLM_MODEL", "google-gla:gemini-1.5-flash")

metadata_agent = Agent(
    model_name,
    output_type=ProductMetadata,
    system_prompt="You are an expert product cataloguer. Analyze the product title and description to extract structured metadata. Identify weight (convert to grams), packaging type (detect Refills vs Containers), and Category.",
)


def run_metadata_extraction(name: str, description: str) -> ProductMetadata:
    """
    Extracts metadata from text using LLM.
    """
    try:
        prompt = f"Product Name: {name}\nDescription: {description or ''}"
        logger.info(f"Extracting metadata for: {name}")

        result = metadata_agent.run_sync(prompt)
        return result.output
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return ProductMetadata()
