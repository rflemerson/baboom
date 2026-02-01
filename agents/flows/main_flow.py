"""Orchestration of the product ingestion pipeline."""

import json
import logging
import os
from enum import Enum

# Setup Django if run as script
if __name__ == "__main__":
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
    django.setup()

from agents.brain.groq_agent import run_groq_json_extraction
from agents.brain.raw_extraction_agent import run_raw_extraction
from agents.storage import get_storage
from agents.tools.scraper import ScraperService
from core.services import product_create
from core.types import ProductComponentInput, ProductCreateInput
from scrapers.models import ScrapedItem

logger = logging.getLogger(__name__)


class PipelineStep(Enum):
    """Enumeration of pipeline steps."""

    DOWNLOAD = "download"
    ANALYZE = "analyze"
    UPLOAD = "upload"
    FULL = "full"


def download_task(item_id: int) -> str:
    """Step 1: Download assets to storage."""
    try:
        item = ScrapedItem.objects.get(id=item_id)
        service = ScraperService()
        storage_path = service.download_assets(item.id, item.product_link)
        # We don't have DOWNLOADED status. Let's use PROCESSING or maybe keep it unchanged?
        # Typically after download we are ready for analysis.
        # For now, let's mark as PROCESSING.
        item.status = ScrapedItem.Status.PROCESSING
        item.save()
        return storage_path
    except Exception as e:
        logger.error(f"Download failed for {item_id}: {e}")
        item = ScrapedItem.objects.get(id=item_id)
        item.status = ScrapedItem.Status.ERROR
        item.last_error_log = str(e)
        item.save()
        raise


def analyze_task(item_id: int, storage_path: str):
    """Step 2: Extract Metadata & Analyze Images with AI."""
    item = ScrapedItem.objects.get(id=item_id)
    service = ScraperService()
    storage = get_storage()

    # 1. Extract Metadata from HTML
    metadata = service.extract_metadata(storage_path, item.product_link)

    # 2. Consolidate Raw Data (Heuristic)
    # Convert Decimal/Strings to appropriate types if needed
    price = float(item.price) if item.price is not None else None
    raw_data = service.consolidate(
        metadata,
        brand_name_override=item.store_slug
        if item.store_slug != "soldiers"
        else "Soldiers Nutrition",
        price=price,
        stock_status=item.stock_status,
    )

    # 3. Select Best Images
    bucket, _ = storage_path.split("/", 1)
    cand_key = "candidates.json"
    candidates = json.loads(storage.download(bucket, cand_key))
    valid_imgs = [c for c in candidates if c["score"] > 0]
    valid_imgs.sort(key=lambda x: x["score"], reverse=True)
    top_images = [f"{bucket}/{c['file']}" for c in valid_imgs[:8]]

    # 4. Raw Extraction (Vision LLM - Gemma/GPT4o)
    logger.info(f"Submitting {len(top_images)} images to Vision Model...")
    raw_text_report = run_raw_extraction(
        name=raw_data.name,
        description=raw_data.description or "",
        image_paths=top_images,
    )

    # 5. Structured Extraction (Groq/Gemini)
    logger.info("Extracting structured JSON...")
    analysis_result = run_groq_json_extraction(raw_text_report)

    return raw_data, analysis_result, top_images


def upload_product_task(item_id: int, raw_data, analysis_result, top_images):
    """Step 3: Create Product in Core."""
    item = ScrapedItem.objects.get(id=item_id)

    # 1. Map Categories to Tags
    tag_paths = analysis_result.tags_hierarchy or []
    if raw_data.category:
        # Add scraped category as a single-level tag if not already present
        # This keeps the scraper's "truth"
        cat_tag = (
            [raw_data.category.name]
            if hasattr(raw_data.category, "name")
            else [str(raw_data.category)]
        )
        if cat_tag not in tag_paths:
            tag_paths.append(cat_tag)

    # 2. Prepare Payload
    # Map 'nutrition_facts' from AnalysisResult -> ProductNutritionProfile schema if needed
    # But product_create expects list of dicts. We need to map `analysis_result.nutrition_facts` to the payload dict.

    nutrition_payload = []
    if analysis_result.nutrition_facts:
        nf = analysis_result.nutrition_facts

        # Micros mapping
        micros = []
        if nf.micronutrients:
            for m in nf.micronutrients:
                micros.append({"name": m.name, "value": float(m.value), "unit": m.unit})

        nutrition_entry = {
            "flavor_names": analysis_result.flavor_names,
            "nutrition_facts": {
                "description": "Information from AI Analysis",
                "serving_size_grams": float(nf.serving_size_grams),
                "energy_kcal": nf.energy_kcal,
                "proteins": float(nf.proteins),
                "carbohydrates": float(nf.carbohydrates),
                "total_sugars": float(nf.total_sugars),
                "added_sugars": float(nf.added_sugars),
                "total_fats": float(nf.total_fats),
                "saturated_fats": float(nf.saturated_fats),
                "trans_fats": float(nf.trans_fats),
                "dietary_fiber": float(nf.dietary_fiber),
                "sodium": float(nf.sodium),
                "micronutrients": micros,
            },
        }
        nutrition_payload.append(nutrition_entry)

    # 3. Combo Components Mapping
    components_payload = []
    if analysis_result.is_combo and analysis_result.components:
        for comp in analysis_result.components:
            components_payload.append(
                ProductComponentInput(
                    name=comp.name,
                    quantity=comp.quantity,
                    weight_hint=comp.weight_hint,
                    packaging_hint=comp.packaging_hint,
                )
            )

    # 4. Construct Input
    input_data = ProductCreateInput(
        name=analysis_result.name or raw_data.name,
        weight=analysis_result.weight_grams or 0,
        brand_name=raw_data.brand_name or "Unknown Brand",
        category_path=analysis_result.category_hierarchy,
        ean=raw_data.ean or None,
        description=raw_data.description,
        packaging=analysis_result.packaging,
        is_published=False,  # Draft by default
        tag_paths=tag_paths,  # List[List[str]] passed directly? ProductCreateInput expects List[str] OR List[List[str]].
        # Wait, ProductCreateInput.tags type: list[str] | list[list[str]] | None.
        # But core.services._resolve_tags handles list[list[str]].
        tags=tag_paths,
        stores=[
            {
                "store_name": item.store_slug
                if item.store_slug != "soldiers"
                else "Soldiers Nutrition",
                "product_link": item.product_link,
                "price": float(item.price) if item.price else 0.0,
                "stock_status": item.stock_status,
                "external_id": item.external_id,
            }
        ],
        nutrition=nutrition_payload,
        # New Enriched Fields
        is_combo=analysis_result.is_combo,
        components=components_payload,
        nutrient_claims=analysis_result.nutrient_claims,
    )

    # 5. Create
    try:
        product = product_create(data=input_data)
        logger.info(f"Product created: {product.name} (ID: {product.id})")

        # Link ScrapedItem
        item.status = ScrapedItem.Status.LINKED
        # We need to link the store manually? product_create does specific store linking inside.
        # But we need to link the ScrapedItem object to the ProductStore created.
        # For now, just marking LINKED is enough for flow.
        item.save()
        return product
    except Exception as e:
        logger.error(f"Creation failed: {e}")
        raise


def product_ingestion_flow(
    target_item_id: int,
    dry_run: bool = False,
    batch_size: int = 1,
    step: PipelineStep = PipelineStep.FULL,
):
    """Orchestrates the ingestion pipeline."""
    items = []
    if target_item_id:
        items = list(ScrapedItem.objects.filter(id=target_item_id))
    else:
        # Status.NEW is the correct 'pending' state
        # Status.PROCESSING might be used for downloaded items, but let's check tasks.py logic
        # For this flow, we assume NEW items need download, and DOWNLOADED ones need analysis.
        # But wait, the model doesn't have DOWNLOADED status.
        # Let's check status definition again.
        # Status: NEW, PROCESSING, LINKED, ERROR, DISCARDED, REVIEW, IGNORED.
        # So we probably use PROCESSING as intermediate.

        # Let's stick to simple logic: Filter NEW for full flow.
        items = list(
            ScrapedItem.objects.filter(status=ScrapedItem.Status.NEW)[:batch_size]
        )

    logger.info(f"Processing {len(items)} items...")

    for item in items:
        try:
            storage_path = ""
            if step in [PipelineStep.DOWNLOAD, PipelineStep.FULL]:
                storage_path = download_task(item.id)
            else:
                # If skipping download, assume default path structure
                storage_path = f"{item.id}/source.html"

            if step == PipelineStep.DOWNLOAD:
                continue

            if step in [PipelineStep.ANALYZE, PipelineStep.FULL]:
                raw, result, imgs = analyze_task(item.id, storage_path)

                if dry_run:
                    logger.info("DRY RUN: Analysis complete. Result:")
                    logger.info(result.model_dump_json(indent=2))
                    continue

                if step in [PipelineStep.UPLOAD, PipelineStep.FULL] and not dry_run:
                    upload_product_task(item.id, raw, result, imgs)

        except Exception as e:
            logger.error(f"Flow failed for item {item.id}: {e}")


if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Baboom Ingestion Flow CLI")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target-item-id", type=int)
    parser.add_argument(
        "--step",
        type=str,
        default="full",
        choices=["download", "analyze", "upload", "full"],
    )

    args = parser.parse_args()

    product_ingestion_flow(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        target_item_id=args.target_item_id,
        step=PipelineStep(args.step),
    )
