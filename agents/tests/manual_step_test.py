import argparse
import json
import logging
import os

import django
from dotenv import load_dotenv

# Setup Environment
load_dotenv()
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
    django.setup()

from agents.brain.groq_agent import run_groq_json_extraction  # noqa: E402
from agents.brain.raw_extraction_agent import run_raw_extraction  # noqa: E402
from agents.storage import get_storage  # noqa: E402
from agents.tools.scraper import ScraperService  # noqa: E402
from scrapers.models import ScrapedItem  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_item_dir(item_id):
    path = f"temp/{item_id}"
    os.makedirs(path, exist_ok=True)
    return path


def step_download(item_id):
    logger.info(f"--- STEP 1: DOWNLOAD & ASSET MIRRORING (Item {item_id}) ---")
    item = ScrapedItem.objects.get(id=item_id)
    service = ScraperService()

    # This downloads to the configured storage and returns the base path
    storage_base = service.download_assets(item.id, item.product_link)

    # Mirroring to local temp/ id for visibility
    item_dir = get_item_dir(item_id)
    storage = get_storage()
    bucket, _ = storage_base.split("/", 1)

    # 1. HTML
    html_key = "source.html"
    if storage.exists(bucket, html_key):
        content = storage.download(bucket, html_key)
        with open(os.path.join(item_dir, "source.html"), "wb") as f:
            f.write(content)

    # 2. Metadata (download_assets saves data.json)
    meta_key = "data.json"
    if storage.exists(bucket, meta_key):
        content = storage.download(bucket, meta_key)
        with open(os.path.join(item_dir, "extracted_metadata.json"), "wb") as f:
            f.write(content)

    # 3. Candidates
    cand_key = "candidates.json"
    if storage.exists(bucket, cand_key):
        content = storage.download(bucket, cand_key)
        with open(os.path.join(item_dir, "candidates.json"), "wb") as f:
            f.write(content)

    # 4. Images
    if storage.exists(bucket, cand_key):
        content = storage.download(bucket, cand_key)
        candidates = json.loads(content)
        img_dir = os.path.join(item_dir, "images")
        os.makedirs(img_dir, exist_ok=True)
        for c in candidates:
            if storage.exists(bucket, c["file"]):
                img_data = storage.download(bucket, c["file"])
                with open(os.path.join(item_dir, c["file"]), "wb") as f:
                    f.write(img_data)

    logger.info(f"Assets mirrored to {item_dir}")


def step_metadata(item_id):
    logger.info(f"--- STEP 2: METADATA EXTRACTION (Item {item_id}) ---")
    item_dir = get_item_dir(item_id)
    cand_path = os.path.join(item_dir, "candidates.json")
    meta_path = os.path.join(item_dir, "extracted_metadata.json")

    if not os.path.exists(cand_path) or not os.path.exists(meta_path):
        logger.error("Run 'download' step first.")
        return

    with open(meta_path) as f:
        meta = json.load(f)

    service = ScraperService()
    item = ScrapedItem.objects.get(id=item_id)

    # Cast Decimal to float for compatibility
    price_val = float(item.price) if item.price is not None else None

    result = service.consolidate(
        meta,
        brand_name_override=item.store_slug
        if item.store_slug != "soldiers"
        else "Soldiers Nutrition",
        price=price_val,
        stock_status=item.stock_status,
    )

    # Save the consolidated result
    cons_path = os.path.join(item_dir, "consolidated_scraped.json")
    with open(cons_path, "w") as f:
        f.write(result.model_dump_json(indent=2))

    logger.info(f"Consolidated metadata saved to {cons_path}")
    logger.info(f"Name: {result.name}")
    logger.info(f"EAN: {result.ean}")


def step_images(item_id):
    logger.info(f"--- STEP 3: IMAGE FILTERING & SELECTION (Item {item_id}) ---")
    item_dir = get_item_dir(item_id)
    cand_path = os.path.join(item_dir, "candidates.json")

    if not os.path.exists(cand_path):
        logger.error("Run 'download' step first.")
        return

    with open(cand_path) as f:
        candidates = json.load(f)

    valid = [c for c in candidates if c["score"] > 0]
    valid.sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"Found {len(candidates)} total images.")
    logger.info(f"After filtering (SVG, Size), {len(valid)} images remain.")

    for i, c in enumerate(valid[:10]):
        logger.info(f"  #{i + 1}: {c['file']} (Score: {c['score']})")


def step_raw(item_id):
    logger.info(f"--- STEP 4: RAW EXTRACTION - GEMMA 3 (Item {item_id}) ---")
    item_dir = get_item_dir(item_id)
    cons_path = os.path.join(item_dir, "consolidated_scraped.json")
    cand_path = os.path.join(item_dir, "candidates.json")

    if not os.path.exists(cons_path) or not os.path.exists(cand_path):
        logger.error("Run steps 'download' and 'metadata' first.")
        return

    with open(cons_path) as f:
        raw_data_dict = json.load(f)

    with open(cand_path) as f:
        candidates = json.load(f)

    valid = [c for c in candidates if c["score"] > 0]
    valid.sort(key=lambda x: x["score"], reverse=True)

    image_paths = [f"{item_id}/{c['file']}" for c in valid[:10]]

    logger.info(f"Submitting {len(image_paths)} images to Gemma...")
    raw_text = run_raw_extraction(
        name=raw_data_dict["name"],
        description=raw_data_dict.get("description", ""),
        image_paths=image_paths,
    )

    output_path = os.path.join(item_dir, "raw_extraction.md")
    with open(output_path, "w") as f:
        f.write(raw_text)

    logger.info(f"Raw Markdown saved to {output_path}")


def step_structured(item_id):
    logger.info(f"--- STEP 5: STRUCTURED EXTRACTION - GROQ (Item {item_id}) ---")
    item_dir = get_item_dir(item_id)
    raw_path = os.path.join(item_dir, "raw_extraction.md")

    if not os.path.exists(raw_path):
        logger.error("Run step 'raw' first.")
        return

    with open(raw_path) as f:
        raw_text = f.read()

    logger.info("Submitting raw text to Groq...")
    result_obj = run_groq_json_extraction(raw_text)

    output_path = os.path.join(item_dir, "analysis_result.json")
    with open(output_path, "w") as f:
        f.write(result_obj.model_dump_json(indent=2))

    logger.info(f"Final JSON saved to {output_path}")
    logger.info(f"Category Hierarchy: {result_obj.category_hierarchy}")


def main():
    parser = argparse.ArgumentParser(description="Structured Pipeline Testing")
    parser.add_argument(
        "step",
        choices=["download", "metadata", "images", "raw", "structured", "full"],
        help="Step to run",
    )
    parser.add_argument("item_id", type=int, help="ScrapedItem ID to test")

    args = parser.parse_args()

    if args.step == "download":
        step_download(args.item_id)
    elif args.step == "metadata":
        step_metadata(args.item_id)
    elif args.step == "images":
        step_images(args.item_id)
    elif args.step == "raw":
        step_raw(args.item_id)
    elif args.step == "structured":
        step_structured(args.item_id)
    elif args.step == "full":
        step_download(args.item_id)
        step_metadata(args.item_id)
        step_images(args.item_id)
        step_raw(args.item_id)
        step_structured(args.item_id)


if __name__ == "__main__":
    main()
