import logging
import os

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

from ..schemas.metadata import ProductMetadata

load_dotenv()
logger = logging.getLogger(__name__)

model_name = os.getenv("LLM_MODEL", "google-gla:gemini-1.5-flash")

metadata_agent = Agent(
    model_name,
    output_type=ProductMetadata,
    deps_type=str,
    system_prompt="""Você é um especialista em catálogo de suplementos.
Analise o título e a descrição do produto para extrair metadados estruturados.

REGRAS:
1. Peso: Extraia o peso total e converta para gramas.
2. Embalagem: Detecte se é POTE (CONTAINER), REFIL (REFILL), BARRA (BAR) ou OUTRO (OTHER).
3. CATEGORIA (HIERARQUIA): Retorne uma lista representando o caminho na árvore (ex: ["Proteína", "Whey", "Isolado"]).
4. TAGS (HIERARQUIA): Retorne uma LISTA DE LISTAS. Cada sub-lista é um caminho hierárquico (ex: [["Proteína", "Whey"], ["Dieta", "Low Carb"]]).

CONTEXTO DE TAXONOMIA EXISTENTE:
{taxonomy_context}

Use preferencialmente as categorias e tags acima se forem aplicáveis. Se criar novas, siga o mesmo padrão de hierarquia.""",
)


@metadata_agent.system_prompt
def get_taxonomy_context(ctx: RunContext[str]) -> str:
    return f"Categorias e Tags atuais para contexto:\n{ctx.deps}"


def run_metadata_extraction(
    name: str,
    description: str,
    existing_categories: list[str] | None = None,
    existing_tags: list[str] | None = None,
) -> ProductMetadata:
    """
    Extracts metadata from text using LLM, respecting existing taxonomy.
    """
    try:
        categories_str = ", ".join(existing_categories or [])
        tags_str = ", ".join(existing_tags or [])
        taxonomy_context = (
            f"Categorias Disponíveis: {categories_str}\nTags Disponíveis: {tags_str}"
        )

        prompt = f"Product Name: {name}\nDescription: {description or ''}"
        logger.info(f"Extracting metadata for: {name}")

        result = metadata_agent.run_sync(prompt, deps=taxonomy_context)
        return result.output
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return ProductMetadata()
