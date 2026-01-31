import json

from dagster import AssetExecutionContext, Config, MetadataValue, asset

from .brain.groq_agent import run_groq_json_extraction

# Import your schemas and logics
from .brain.raw_extraction_agent import run_raw_extraction
from .resources import AgentClientResource, ScraperServiceResource, StorageResource
from .schemas.product import RawScrapedData


# Configuração para rodar um item específico
class ItemConfig(Config):
    """Configuration for running a specific item."""

    item_id: int
    url: str
    store_slug: str = "unknown"


# --- ASSET 1: ARQUIVOS NO DISCO (HTML/Imagens) ---
@asset
def downloaded_assets(
    context: AssetExecutionContext,
    config: ItemConfig,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
):
    """
    Baixa o HTML e as imagens para a pasta local temp/{id}.

    Retorna o caminho do bucket no storage.
    """
    service = scraper.get_service()
    api = client.get_client()

    context.log.info(f"📥 Baixando item {config.item_id} de {config.url}")

    try:
        # Sua lógica existente de download
        storage_path = service.download_assets(config.item_id, config.url)

        # Dagster UI: Mostra o caminho e a URL como metadados clicáveis
        context.add_output_metadata(
            {"path": storage_path, "url": MetadataValue.url(config.url)}
        )

        return storage_path
    except Exception as e:
        context.log.error(f"Download failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


# --- ASSET 2: METADADOS BRUTOS (Extração Leve) ---
@asset
def scraped_metadata(
    context: AssetExecutionContext,
    config: ItemConfig,
    scraper: ScraperServiceResource,
    client: AgentClientResource,
    downloaded_assets: str,
) -> RawScrapedData:
    """Lê o HTML baixado e extrai JSON-LD/OpenGraph."""
    service = scraper.get_service()
    api = client.get_client()

    # Usa o output do asset anterior (downloaded_assets)
    storage_path = downloaded_assets

    try:
        context.log.info(f"🧬 Extraindo metadados de {storage_path}")
        meta_dict = service.extract_metadata(storage_path, config.url)

        # Consolida
        raw_data = service.consolidate(meta_dict, brand_name_override=config.store_slug)

        # Dagster UI: Mostra o nome encontrado
        context.add_output_metadata({"product_name": raw_data.name})

        return raw_data
    except Exception as e:
        context.log.error(f"Metadata extraction failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


# --- ASSET 3: OCR (Gemma / Visão) ---
@asset
def ocr_extraction(
    context: AssetExecutionContext,
    config: ItemConfig,
    storage: StorageResource,
    client: AgentClientResource,
    scraped_metadata: RawScrapedData,
    downloaded_assets: str,
) -> str:
    """Usa o Gemma 3 para ler as imagens baixadas."""
    store = storage.get_storage()
    api = client.get_client()

    bucket, _ = downloaded_assets.split("/", 1)

    try:
        # Lógica de carregar imagens (reusada do seu código)
        candidates_key = "candidates.json"
        image_paths = []

        if store.exists(bucket, candidates_key):
            data = store.download(bucket, candidates_key)
            candidates = json.loads(data)
            # Filtra Top 5
            valid = sorted(
                [c for c in candidates if c["score"] > 0],
                key=lambda x: x["score"],
                reverse=True,
            )[:5]
            image_paths = [f"{bucket}/{c['file']}" for c in valid]

        context.log.info(f"👁️ Rodando Gemma em {len(image_paths)} imagens...")

        raw_text = run_raw_extraction(
            name=scraped_metadata.name,
            description=scraped_metadata.description or "",
            image_paths=image_paths,
        )

        # Dagster UI: Mostra prévia do texto
        context.add_output_metadata(
            {"text_preview": MetadataValue.md(raw_text[:500] + "...")}
        )

        return raw_text
    except Exception as e:
        context.log.error(f"OCR extraction failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


# --- ASSET 4: JSON FINAL (Groq) ---
@asset
def product_analysis(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    ocr_extraction: str,
) -> dict:
    """Usa o Llama 3 (Groq) para estruturar o texto em JSON."""
    api = client.get_client()

    try:
        context.log.info("🧠 Estruturando JSON com Groq...")
        result = run_groq_json_extraction(ocr_extraction)

        return result.model_dump(by_alias=True)
    except Exception as e:
        context.log.error(f"Product analysis failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=False)
        raise


# --- ASSET 5: UPLOAD (Finalização) ---
@asset
def upload_to_api(
    context: AssetExecutionContext,
    config: ItemConfig,
    client: AgentClientResource,
    product_analysis: dict,
    scraped_metadata: RawScrapedData,
):
    """Envia o produto pronto para a API do Baboom."""
    api = client.get_client()

    context.log.info(f"🚀 Enviando {scraped_metadata.name} para o Banco de Dados...")

    try:
        # Reconstruct nutrition profile from raw analysis dict
        # Since product_analysis is a dict (returned by Asset 4)
        analysis_data = product_analysis

        nutrition_profiles = []
        if analysis_data.get("nutrition_facts"):
            nutrition_profiles.append(
                {
                    "nutritionFacts": analysis_data["nutrition_facts"],
                    "flavorNames": analysis_data.get("flavor_names", []),
                }
            )

        stock_map = {"A": "AVAILABLE", "L": "LAST_UNITS", "O": "OUT_OF_STOCK"}

        payload = {
            "name": analysis_data.get("name") or scraped_metadata.name,
            "brandName": scraped_metadata.brand_name,
            "weight": int(analysis_data.get("weight_grams") or 0),
            "ean": scraped_metadata.ean,
            "description": scraped_metadata.description,
            "packaging": analysis_data.get("packaging") or "CONTAINER",
            "originScrapedItemId": int(config.item_id),
            "stores": [
                {
                    "storeName": config.store_slug,  # Using slug as name for now or could fetch more from config
                    "productLink": config.url,
                    "price": float(scraped_metadata.price or 0.0),
                    "externalId": "",  # Could be added to config if available
                    "stockStatus": stock_map.get(
                        scraped_metadata.stock_status or "A", "AVAILABLE"
                    ),
                }
            ],
            "nutrition": nutrition_profiles,
            "categoryPath": analysis_data.get("category_hierarchy") or [],
            "tagPaths": [
                {"path": tp} for tp in (analysis_data.get("tags_hierarchy") or [])
            ],
            "isPublished": True,
        }

        api.create_product(payload)
    except Exception as e:
        context.log.error(f"Upload failed: {e}")
        api.report_error(config.item_id, str(e), is_fatal=True)
        raise

    return "OK"
