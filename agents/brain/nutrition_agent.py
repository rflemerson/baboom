import logging
import os

from dotenv import load_dotenv
from pydantic_ai import Agent, BinaryContent

from ..schemas.nutrition import NutritionFacts, ProductNutritionProfile
from ..storage import get_storage

load_dotenv()

logger = logging.getLogger(__name__)

model_name = os.getenv("LLM_MODEL", "google-gla:gemini-1.5-flash")

nutrition_agent = Agent(
    model_name,
    output_type=NutritionFacts,
    system_prompt="Você é um especialista em nutrição. Extraia os fatos nutricionais de imagens com precisão absoluta. Retorne os valores por PORÇÃO.",
)


def run_nutrition_extraction(storage_path: str) -> list[ProductNutritionProfile]:
    """
    Runs the agent to extract nutrition data from an image file in storage.
    storage_path is expected to be "bucket/key".
    """
    storage = get_storage()
    try:
        bucket, key = storage_path.split("/", 1)
    except ValueError:
        logger.error(f"Invalid storage path: {storage_path}")
        return []

    if not storage.exists(bucket, key):
        logger.warning(f"Image not found in storage: {storage_path}")
        return []

    try:
        image_data = storage.download(bucket, key)

        logger.info(f"Sending image from storage to PydanticAI Agent ({model_name})...")

        result = nutrition_agent.run_sync(
            [
                "Extraia a tabela nutricional desta imagem. Use os valores por porção.",
                BinaryContent(data=image_data, media_type="image/jpeg"),
            ]
        )
        # Wrap the single facts object into the expected list of profiles
        return [ProductNutritionProfile(nutrition_facts=result.output, flavor_names=[])]
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return []
