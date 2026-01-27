import logging

from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel

from ..schemas.analysis import ProductAnalysisResult

logger = logging.getLogger(__name__)

# Llama 3.3 70B Versatile (128k context, nice for JSON)
MODEL_NAME = "llama-3.3-70b-versatile"


def get_groq_agent():
    model = GroqModel(MODEL_NAME)

    return Agent(
        model,
        output_type=ProductAnalysisResult,
        system_prompt="""OBJECTIVE:
You are a Data Extraction Expert.
You will receive a RAW TEXT REPORT describing a product (extracted from images/text).
Your job is to CONVERT this text into a VALID JSON object matching the schema.

RULES:
1. Extract 'category_hierarchy' based on the product type.
   - Example: ["Suplementos", "Proteínas", "Whey Protein", "Blend"]
2. Extract 'tags_hierarchy' from keywords.
   - Example: [["Marca", "Black Skull"], ["Tipo", "Whey"], ["Característica", "Isolado"]]
   - MUST be a list of lists of STRINGS. do NOT use numbers.
3. Extract 'nutrition_facts' precisely.
   - For 'flavor_names' inside nutrition, use EMPTY LIST [] if none, known. NEVER use null.
   - Convert units if needed (keep standard).
4. Extract 'flavor_names' (Root field).
   - If multiple flavors are listed (e.g. "Available in Chocolate, Strawberry"), list them ALL.

OUTPUT STRICT JSON only. Do not wrap in markdown blocks if not supported.""",
    )


def run_groq_json_extraction(raw_text: str) -> ProductAnalysisResult:
    """
    Runs Groq (Llama 3.3) to convert raw text -> JSON Schema.
    """
    logger.info(f"Running Groq ({MODEL_NAME}) on {len(raw_text)} chars of text...")

    agent = get_groq_agent()

    try:
        result = agent.run_sync(raw_text)
        return result.output
    except Exception as e:
        logger.error(f"Groq output extraction failed: {e}")
        raise
