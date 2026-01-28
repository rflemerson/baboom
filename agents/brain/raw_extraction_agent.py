import logging

from pydantic_ai import Agent, BinaryContent

logger = logging.getLogger(__name__)

# Explicitly using Gemma-3-27b-it as requested
MODEL_NAME = "google-gla:gemma-3-27b-it"

raw_extraction_agent = Agent(
    MODEL_NAME,
    # System prompt not supported by Gemma 3 via API
)


def run_raw_extraction(
    name: str,
    description: str,
    image_paths: list[str],
) -> str:
    """
    Runs Gemma-3-27b-it to extract raw text data from multimodal input.
    """
    from ..storage import get_storage

    storage = get_storage()

    INSTRUCTIONS = """OBJETIVO:
Analise as IMAGENS (Rótulo, Tabela Nutricional) e o TEXTO fornecidos.
Extraia TUDO o que puder sobre o produto e Organize em um TEXTO ESTRUTURADO (Markdown).
Não invente nada. Se não estiver visível, não inclua.

SEUS TÓPICOS DEVEM SER:

1. NOME COMPLETO E VARIAÇÕES
   - Nome principal, subtítulos, slogans.

2. METADADOS VISUAIS
   - Peso líquido (ex: 900g, 1.8kg)
   - Tipo de Embalagem (Pote, Refil, Saco, Barra)
   - Marca/Fabricante

3. CATEGORIZAÇÃO (Inferred Hierarchy)
   - Extraia a categoria seguindo uma árvore lógica.
   - Para PROTEÍNAS, use obrigatoriamente: ["Proteína", <Origem: Animal/Vegetal>, <Tipo: Whey/Caseína/Soja/etc>, <Processo: Isolado/Concentrado/Hidrolisado/Blend>]
   - Exemplo 1: ["Proteína", "Animal", "Whey", "Isolado"]
   - Exemplo 2: ["Proteína", "Vegetal", "Ervilha", "Concentrado"]
   - Para outros produtos, siga lógica similar (ex: ["Aminoácido", "Creatina", "Monohidratada"]).

4. SABORES DISPONÍVEIS
   - Liste todos os sabores que você vê na imagem ou texto.

5. TABELA NUTRICIONAL COMPLETA
   - Extraia TODOS os campos obrigatórios da legislação brasileira:
     - Porção de referência (ex: 30g, 2 scoops)
     - Valor Energético (kcal e kJ)
     - Carboidratos (g) e Açúcares (Totais/Adicionados)
     - Proteínas (g)
     - Gorduras Totais, Saturadas, Trans (g)
     - Fibra Alimentar (g)
     - Sódio (mg)
   - Além disso, liste TODOS os Micronutrientes, Vitaminas, Minerais e Aminoácidos visíveis.

6. INGREDIENTES E ALÉRGICOS
   - Lista de ingredientes (se legível)
   - Alertas de alérgicos (Contém Glúten, Leite, Soja, etc)

SAÍDA SOMENTE O TEXTO ORGANIZADO. SEM PREÂMBULOS."""

    # Prepare Inputs - Instructions first
    user_content: list[str | BinaryContent] = [
        INSTRUCTIONS
        + f"\n\n---\nProduct Name: {name}\nDescription: {description or ''}"
    ]

    # Load Images
    loaded_images = 0
    for path in image_paths:
        try:
            bucket, key = path.split("/", 1)
            # Handle potential bucket mismatch if path is like "2/images/..." and bucket is "2"
            # (Logic copied from product_agent, might need adjustment if storage backend differs)

            if storage.exists(bucket, key):
                img_data = storage.download(bucket, key)
                # Gemma 3 supports images
                user_content.append(
                    BinaryContent(data=img_data, media_type="image/jpeg")
                )
                loaded_images += 1
        except Exception as e:
            logger.warning(f"Failed to load image for raw extraction {path}: {e}")

    logger.info(
        f"Raw Extraction: {name} | Model: {MODEL_NAME} | Images: {loaded_images}"
    )

    try:
        result = raw_extraction_agent.run_sync(user_content)
        # Debugging what result contains
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result dir: {dir(result)}")

        if hasattr(result, "data"):
            return result.data
        if hasattr(result, "output"):
            return result.output
        return str(result)
    except Exception as e:
        logger.error(f"Raw extraction failed: {e}")
        return f"ERROR: {e!s}"
