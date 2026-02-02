"""Orchestration of the product ingestion pipeline."""

import json
import logging
from enum import Enum

from dotenv import load_dotenv

from agents.brain.groq_agent import run_groq_json_extraction
from agents.brain.raw_extraction_agent import run_raw_extraction
from agents.client import AgentClient
from agents.storage import get_storage
from agents.tools.scraper import ScraperService

load_dotenv()

load_dotenv()

logger = logging.getLogger(__name__)


class PipelineStep(Enum):
    """Enumeration of pipeline steps."""

    DOWNLOAD = "download"
    ANALYZE = "analyze"
    UPLOAD = "upload"
    FULL = "full"


def download_task(item_id: int):
    """Step 1: Download Assets."""
    client = AgentClient()

    # 1. Checkout item (get URL and Metadata)
    item_data = client.checkout_work(target_item_id=item_id, force=True)
    if not item_data:
        raise Exception(f"Could not checkout item {item_id}")

    logger.info(f"Checked out item {item_id}: {item_data.get('productLink')}")

    # 2. Download Assets via ScraperService
    service = ScraperService()
    storage_path = service.download_assets(item_id, item_data["productLink"])
    return storage_path, item_data


def analyze_task(item_id: int, storage_path: str, item_data: dict):
    """Step 2: Analysis."""
    service = ScraperService()
    storage = get_storage()

    # 1. Metadata
    metadata = service.extract_metadata(storage_path, item_data["productLink"])

    # 2. Consolidate
    price = item_data.get("price")
    stock_status = item_data.get("stockStatus")

    raw_data = service.consolidate(
        metadata,
        brand_name_override=item_data.get("storeSlug"),
        price=float(price) if price else None,
        stock_status=stock_status,
    )

    # 3. Images
    bucket, _ = storage_path.split("/", 1)
    cand_key = "candidates.json"
    candidates_json = storage.download(bucket, cand_key)
    candidates = json.loads(candidates_json)

    valid_imgs = [c for c in candidates if c["score"] > 0]
    valid_imgs.sort(key=lambda x: x["score"], reverse=True)
    top_images = [f"{bucket}/{c['file']}" for c in valid_imgs[:8]]

    # 4. Raw Extraction
    raw_text = run_raw_extraction(
        item_data.get("productLink"), raw_data.description or "", top_images
    )

    # 5. Groq Analysis
    analysis_result = run_groq_json_extraction(raw_text)

    return raw_data, analysis_result, top_images


def upload_product_task(
    item_id: int, raw_data, analysis_result, top_images, item_data: dict
):
    """Step 3: Upload via GraphQL."""
    client = AgentClient()

    # Construct Payload matching ProductInput
    payload = {
        "name": analysis_result.name or raw_data.name,
        "weight": int(analysis_result.weight_grams or 0),
        "brandName": raw_data.brand_name or "Unknown Brand",
        "categoryName": analysis_result.category_hierarchy[-1]
        if analysis_result.category_hierarchy
        else (raw_data.category if raw_data.category else None),
        "ean": raw_data.ean,
        "description": raw_data.description,
        "packaging": analysis_result.packaging,
        "isPublished": False,
        "tags": [],
        "stores": [
            {
                "storeName": item_data.get("storeName", "Unknown"),
                "productLink": item_data.get("productLink"),
                "price": float(item_data.get("price") or 0),
                "stockStatus": "AVAILABLE"
                if item_data.get("stockStatus") in ["A", "AVAILABLE"]
                else "OUT_OF_STOCK",
                "externalId": item_data.get("externalId"),
                "affiliateLink": "",
            }
        ],
        "originScrapedItemId": int(item_id),
        "isCombo": analysis_result.is_combo,
        "nutrientClaims": analysis_result.nutrient_claims,
        "nutrition": [],
    }

    # Tags
    flat_tags = []
    if analysis_result.tags_hierarchy:
        flat_tags.extend(
            [tag for path in analysis_result.tags_hierarchy for tag in path]
        )
    if analysis_result.nutrient_claims:
        flat_tags.extend(analysis_result.nutrient_claims)

    payload["tags"] = list(set(flat_tags))

    # Nutrition
    if analysis_result.nutrition_facts:
        nf = analysis_result.nutrition_facts
        micros = []
        if nf.micronutrients:
            for m in nf.micronutrients:
                micros.append({"name": m.name, "value": float(m.value), "unit": m.unit})

        payload["nutrition"] = [
            {
                "flavorNames": analysis_result.flavor_names,
                "nutritionFacts": {
                    "description": "AI Analysis",
                    "servingSizeGrams": int(nf.serving_size_grams),
                    "energyKcal": int(nf.energy_kcal),
                    "proteins": float(nf.proteins),
                    "carbohydrates": float(nf.carbohydrates),
                    "totalSugars": float(nf.total_sugars),
                    "addedSugars": float(nf.added_sugars),
                    "totalFats": float(nf.total_fats),
                    "saturatedFats": float(nf.saturated_fats),
                    "transFats": float(nf.trans_fats),
                    "dietaryFiber": float(nf.dietary_fiber),
                    "sodium": int(nf.sodium),
                    "micronutrients": micros,
                },
            }
        ]

    # Submit
    try:
        result = client.create_product(payload)
        logger.info(f"Product created: {result}")
        return result
    except Exception as e:
        client.report_error(item_id, str(e), is_fatal=False)
        raise


def product_ingestion_flow(target_item_id: int, step: PipelineStep = PipelineStep.FULL):
    """Execute the pipeline."""
    client = AgentClient()
    try:
        storage_path, item_data = download_task(target_item_id)

        if step == PipelineStep.DOWNLOAD:
            return

        raw, analysis, imgs = analyze_task(target_item_id, storage_path, item_data)

        if step == PipelineStep.ANALYZE:
            return

        upload_product_task(target_item_id, raw, analysis, imgs, item_data)

    except Exception as e:
        logger.error(f"Flow failed: {e}")
        client.report_error(target_item_id, f"Flow failed: {e}", is_fatal=True)
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", type=int, required=True)
    parser.add_argument("--step", type=str, default="full")
    args = parser.parse_args()

    product_ingestion_flow(args.item_id, PipelineStep(args.step))
