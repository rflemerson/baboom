import logging
import os

from dotenv import load_dotenv
from pydantic_ai import Agent, BinaryContent, RunContext

from ..schemas.analysis import ProductAnalysisResult
from ..storage import get_storage

load_dotenv()
logger = logging.getLogger(__name__)

model_name = os.getenv("LLM_MODEL", "google-gla:gemini-2.5-flash-lite")

product_agent = Agent(
    model_name,
    output_type=ProductAnalysisResult,
    deps_type=str,
    system_prompt="""OBJETIVO:
Analise o TEXTO (Nome, Descrição) e as IMAGENS fornecidas para extrair um perfil completo e preciso do produto.

1. METADADOS E HIERARQUIA:
   - PESO (weight_grams): Extraia o peso total em gramas (ex: "Whey 900g" -> 900).
   - EMBALAGEM (packaging): Identifique visualmente ou por texto. Tipos: POTE (CONTAINER), REFIL (REFILL), BARRA (BAR), OUTRO (OTHER).
   - CATEGORIA (category_hierarchy): Caminho hierárquico único (ex: ["Suplementos", "Proteínas", "Whey Protein", "Isolado"]). Use a taxonomia existente se possível.
   - TAGS (tags_hierarchy): Lista de listas descrevendo características (ex: [["Marca", "Black Skull"], ["Destaque", "Zero Carb"]]).

2. IDENTIFICAÇÃO DE SABORES (flavor_names):
   - Use TANTO o texto QUANTO a imagem para identificar todos os sabores.
   - Analise o rótulo principal e a tabela nutricional.
   - Exemplo: ["Baunilha", "Cookies & Cream"]

3. TABELA NUTRICIONAL (nutrition_facts):
   - Identifique a tabela nutricional na imagem.
   - VALORES POR PORÇÃO (serving_size_grams): Use sempre a porção unitária (1 scoop, 30g).
   - Extraia macros (Proteína, Carbo, Gorduras) e micros se visíveis.
   - Se não houver tabela visível, retorne null para este campo.

CONTEXTO DE TAXONOMIA EXISTENTE:
{taxonomy_context}""",
)


@product_agent.system_prompt
def get_taxonomy_context(ctx: RunContext[str]) -> str:
    return f"Categorias e Tags atuais para contexto:\n{ctx.deps}"


def run_product_analysis(
    name: str,
    description: str,
    image_paths: list[str],
    existing_categories: list[str] | None = None,
    existing_tags: list[str] | None = None,
) -> ProductAnalysisResult:
    """
    Runs the multimodal agent to analyze product text and images simultaneously.
    """
    storage = get_storage()

    # Prepare Inputs
    user_content: list[str | BinaryContent] = [
        f"Product Name: {name}\nDescription: {description or ''}"
    ]

    # Load Images
    for path in image_paths:
        try:
            bucket, key = path.split("/", 1)
            if storage.exists(bucket, key):
                img_data = storage.download(bucket, key)
                user_content.append(
                    BinaryContent(data=img_data, media_type="image/jpeg")
                )  # Assuming JPEG for now, could be dynamic
        except Exception as e:
            logger.warning(f"Failed to load image for analysis {path}: {e}")

    # Prepare Context
    categories_str = ", ".join(existing_categories or [])
    tags_str = ", ".join(existing_tags or [])
    taxonomy_context = (
        f"Categorias Disponíveis: {categories_str}\nTags Disponíveis: {tags_str}"
    )

    logger.info(f"Analyzing product separatedly: {name} with {len(image_paths)} images")

    try:
        result = product_agent.run_sync(user_content, deps=taxonomy_context)
        return result.output
    except Exception as e:
        logger.error(f"Product analysis failed: {e}")
        # Return empty result safe fallback
        return ProductAnalysisResult()
