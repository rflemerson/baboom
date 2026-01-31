import json
import logging
import os
from enum import Enum

import django

# Optional: Initialize Django if running standalone
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
    if not os.environ.get("DJANGO_SETTINGS_SKIP_SETUP"):
        django.setup()

from prefect import flow, get_run_logger, task

from ..brain.groq_agent import run_groq_json_extraction
from ..brain.raw_extraction_agent import run_raw_extraction
from ..client import AgentClient
from ..schemas.analysis import ProductAnalysisResult
from ..schemas.nutrition import ProductNutritionProfile
from ..schemas.product import RawScrapedData, ScrapedProductData
from ..storage import get_storage
from ..tools.scraper import ScraperService

logger = logging.getLogger(__name__)


class PipelineStep(str, Enum):
    DOWNLOAD = "download"  # Download assets and basic metadata
    ANALYZE = "analyze"  # Run AI analysis (Gemma + Groq)
    UPLOAD = "upload"  # Upload result to database
    FULL = "full"  # All steps


@task(name="scraper_task", retries=3, retry_delay_seconds=10)
def scraper_task(
    item_id: int,
    url: str,
    store_name: str | None = None,
    price: float | None = None,
    stock_status: str | None = None,
) -> tuple[RawScrapedData, str]:
    """
    Downloads assets and extracts initial metadata using ScraperService.
    """
    service = ScraperService()

    storage_path = service.download_assets(item_id, url)

    metadata = service.extract_metadata(storage_path, url)

    raw_data = service.consolidate(
        metadata,
        brand_name_override=store_name,
        price=price,
        stock_status=stock_status,
    )

    return raw_data, storage_path


@task(name="analyze_product_task", retries=2, retry_delay_seconds=30)
def analyze_product_task(
    raw_data: RawScrapedData,
    storage_base_path: str,
    gemma_model: str | None = None,
    groq_model: str | None = None,
    raw_prompt: str | None = None,
    structured_prompt: str | None = None,
    skip_images: bool = False,
) -> ProductAnalysisResult:
    """
    Orchestrates the AI-driven analysis of the product using multimodal inputs.
    """
    logger = get_run_logger()
    logger.info(f"Analyzing product: {raw_data.name}")

    image_paths = []
    if not skip_images:
        storage = get_storage()
        try:
            bucket, _ = storage_base_path.split("/", 1)
            candidates_key = "candidates.json"

            if storage.exists(bucket, candidates_key):
                candidates_data = storage.download(bucket, candidates_key)
                candidates = json.loads(candidates_data.decode("utf-8"))

                # Use top 10 relevant images for analysis
                valid_candidates = [c for c in candidates if c["score"] > 0]
                valid_candidates.sort(key=lambda x: x["score"], reverse=True)

                for c in valid_candidates[:10]:
                    image_paths.append(f"{bucket}/{c['file']}")
                    logger.info(f"  Selected Image: {c['file']} (Score: {c['score']})")

        except Exception as e:
            logger.warning(f"Failed to load image candidates: {e}")

    raw_text = run_raw_extraction(
        name=raw_data.name,
        description=raw_data.description or "",
        image_paths=image_paths,
        prompt=raw_prompt,
        model_name=gemma_model,
    )

    logger.info("Stage 2: Structured JSON Extraction")
    return run_groq_json_extraction(
        raw_text, prompt=structured_prompt, model_name=groq_model
    )


@task(name="upload_product_task", retries=3, retry_delay_seconds=30)
def upload_product_task(
    item_id: int,
    url: str,
    raw_data: RawScrapedData,
    analysis_result: ProductAnalysisResult,
    store_name: str | None = None,
    external_id: str | None = None,
) -> None:
    """
    Uploads the validated product analysis to the Baboom database.
    """
    logger = get_run_logger()
    client = AgentClient()

    try:
        nutrition_profiles = []
        if analysis_result.nutrition_facts:
            nutrition_profiles.append(
                ProductNutritionProfile(
                    nutrition_facts=analysis_result.nutrition_facts,
                    flavor_names=analysis_result.flavor_names,
                )
            )

        final_product = ScrapedProductData(
            name=analysis_result.name or raw_data.name,
            brand_name=raw_data.brand_name,
            ean=raw_data.ean,
            description=raw_data.description,
            image_url=raw_data.image_url,
            nutrition=nutrition_profiles,
            origin_scraped_item_id=item_id,
            weight=analysis_result.weight_grams or 0,
            packaging=analysis_result.packaging or "CONTAINER",
            category_path=analysis_result.category_hierarchy or [],
            tag_paths=analysis_result.tags_hierarchy or [],
        )

        logger.info(f"Uploading Product: {final_product.name}")

        stock_map = {"A": "AVAILABLE", "L": "LAST_UNITS", "O": "OUT_OF_STOCK"}

        payload = {
            "name": final_product.name,
            "brandName": final_product.brand_name,
            "weight": int(final_product.weight),
            "ean": final_product.ean,
            "description": final_product.description,
            "packaging": final_product.packaging,
            "originScrapedItemId": int(final_product.origin_scraped_item_id),
            "stores": [
                {
                    "storeName": store_name or raw_data.brand_name,
                    "productLink": url,
                    "price": float(raw_data.price or 0.0),
                    "externalId": external_id or "",
                    "stockStatus": stock_map.get(
                        raw_data.stock_status or "A", "AVAILABLE"
                    ),
                }
            ],
            "nutrition": [
                {
                    "nutritionFacts": n.nutrition_facts.model_dump(
                        exclude={"flavor_names"}, exclude_none=True, by_alias=True
                    ),
                    "flavorNames": n.flavor_names,
                }
                for n in (final_product.nutrition or [])
            ],
            "categoryPath": final_product.category_path,
            "tagPaths": [{"path": tp} for tp in final_product.tag_paths],
            "isPublished": True,
        }

        client.create_product(payload)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise


@flow(name="Baboom Product Ingestion")
def product_ingestion_flow(
    batch_size: int = 1,
    gemma_model: str | None = None,
    groq_model: str | None = None,
    dry_run: bool = False,
    force_update: bool = False,
    skip_images: bool = False,
    skip_metadata: bool = False,
    raw_prompt: str | None = None,
    structured_prompt: str | None = None,
    target_item_id: int | None = None,
    step: PipelineStep = PipelineStep.FULL,
):
    """
    Main flow for processing scraped items through the AI pipeline.
    Supports granular execution via the 'step' parameter.
    """
    logger = get_run_logger()
    client = AgentClient()
    processed_count = 0

    while processed_count < batch_size:
        logger.info(f"Checking for work ({processed_count + 1}/{batch_size})...")
        work = client.checkout_work(force=force_update, target_item_id=target_item_id)

        if not work:
            logger.info("No more work items found.")
            break

        item_id = work["id"]
        logger.info(f"Processing Item {item_id}: {work['productLink']}")

        try:
            raw_scraped_data = None
            storage_path = None
            # Step 1: Download & Initial Metadata
            if step in [PipelineStep.DOWNLOAD, PipelineStep.FULL]:
                raw_scraped_data, storage_path = scraper_task(
                    item_id=item_id,
                    url=work["productLink"],
                    store_name=work.get("storeSlug"),
                    price=work.get("price"),
                    stock_status=work.get("stockStatus"),
                )
            else:
                # Reconstruct storage path if skipping download
                storage_path = f"{item_id}/source.html"
                service = ScraperService()
                metadata = service.extract_metadata(storage_path, work["productLink"])
                raw_scraped_data = service.consolidate(
                    metadata,
                    brand_name_override=work.get("storeSlug"),
                    price=work.get("price"),
                    stock_status=work.get("stockStatus"),
                )

            if skip_metadata:
                logger.info("Metadata extraction skipped by user.")

            # Step 2: AI Analysis
            analysis_result = None
            if step in [PipelineStep.ANALYZE, PipelineStep.FULL]:
                analysis_result = analyze_product_task(
                    raw_data=raw_scraped_data,
                    storage_base_path=storage_path,
                    gemma_model=gemma_model,
                    groq_model=groq_model,
                    raw_prompt=raw_prompt,
                    structured_prompt=structured_prompt,
                    skip_images=skip_images,
                )

            # Step 3: Final Upload
            if step in [PipelineStep.UPLOAD, PipelineStep.FULL]:
                if not analysis_result:
                    # Attempt to load previous analysis if only running upload
                    # (In production we usually run FULL, this is for debug/test)
                    logger.warning(
                        "Upload step requires analysis_result. Run ANALYZE first."
                    )
                    continue

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Ingestion of '{analysis_result.name}' simulated successfully."
                    )
                else:
                    upload_product_task(
                        item_id=item_id,
                        url=work["productLink"],
                        raw_data=raw_scraped_data,
                        analysis_result=analysis_result,
                        store_name=work.get("storeName"),
                        external_id=work.get("externalId"),
                    )

            processed_count += 1
            if target_item_id:
                break

        except Exception as e:
            logger.error(f"Flow failed for item {item_id}: {e}")
            client.report_error(item_id, str(e), is_fatal=True)
            processed_count += 1

    logger.info(f"Batch completed. Total items processed: {processed_count}")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    product_ingestion_flow()
