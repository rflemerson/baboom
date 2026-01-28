import json
import logging
import os

import django
from dotenv import load_dotenv

load_dotenv()

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "baboom.settings")
django.setup()

# Imports after django setup
from agents.brain.groq_agent import run_groq_json_extraction  # noqa: E402
from agents.brain.raw_extraction_agent import run_raw_extraction  # noqa: E402
from agents.storage import get_storage  # noqa: E402
from agents.tools.scraper import ScraperService  # noqa: E402
from scrapers.models import ScrapedItem  # noqa: E402

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_pipeline_full(item_ids=None):
    if not item_ids:
        # Items 2, 3, 4, 5, 6
        item_ids = [2, 3, 4, 5, 6]

    base_temp = "temp"
    os.makedirs(base_temp, exist_ok=True)
    storage = get_storage()
    service = ScraperService()

    logger.info(f"Starting Full Pipeline Test on items: {item_ids}")

    for item_id in item_ids:
        try:
            logger.info(f"\nProcessing Item {item_id}...")
            try:
                item = ScrapedItem.objects.get(id=item_id)
            except ScrapedItem.DoesNotExist:
                logger.info(f"  [SKIP] Item {item_id} does not exist in DB.")
                continue

            # Create item specific temp directory
            item_dir = os.path.join(base_temp, str(item_id))
            os.makedirs(item_dir, exist_ok=True)

            bucket = str(item_id)

            # --- 1. Mirror Assets (HTML & Candidates/Images) ---
            logger.info("  Mirroring assets to temp...")

            # 1a. HTML
            # Main code saves as 'source.html'. We verify this.
            html_key = "source.html"
            html_path = os.path.join(item_dir, html_key)

            if storage.exists(bucket, html_key):
                data = storage.download(bucket, html_key)
                with open(html_path, "wb") as f:
                    f.write(data)
            else:
                # Check fallback
                if storage.exists(bucket, "page.html"):
                    html_key = "page.html"
                    data = storage.download(bucket, html_key)
                    with open(os.path.join(item_dir, "page.html"), "wb") as f:
                        f.write(data)
                    html_path = os.path.join(item_dir, "page.html")

            # 1b. Candidates
            candidates_key = "candidates.json"
            candidates_path = os.path.join(item_dir, candidates_key)
            candidates = []
            if storage.exists(bucket, candidates_key):
                data = storage.download(bucket, candidates_key)
                with open(candidates_path, "wb") as f:
                    f.write(data)
                candidates = json.loads(data.decode("utf-8"))

            # 2. Extract Metadata (Stage 0)
            name = item.name or "Unknown Product"
            description = ""

            try:
                meta = service.extract_metadata(
                    f"{bucket}/{html_key}", item.product_link
                )
                name = meta.get("name") or name
                description = meta.get("description") or ""

                with open(os.path.join(item_dir, "extracted_metadata.json"), "w") as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"  [WARN] Failed to parse HTML: {e}")

            # 3. Mirror Images & Prepare Paths
            image_paths = []
            valid = [c for c in candidates if c.get("score", 0) > 0]
            valid.sort(key=lambda x: x.get("score", 0), reverse=True)

            images_dir = os.path.join(item_dir, "images")
            os.makedirs(images_dir, exist_ok=True)

            for c in valid[:10]:
                storage_path = c["file"]
                full_storage_key = storage_path

                if storage.exists(bucket, full_storage_key):
                    img_data = storage.download(bucket, full_storage_key)
                    local_img_name = os.path.basename(storage_path)
                    local_img_path = os.path.join(images_dir, local_img_name)
                    with open(local_img_path, "wb") as f:
                        f.write(img_data)
                    full_path_for_agent = f"{bucket}/{storage_path}"
                    image_paths.append(full_path_for_agent)

            # --- STAGE 1: RAW EXTRACTION (Gemma) ---
            logger.info("  [Stage 1] Running Gemma-3-27b-it (Text Extraction)...")
            raw_text = ""

            # Optim: Check if already validated run exists to save time/quota?
            # User wants to test new flow, so let's run it.
            if image_paths:
                raw_text = run_raw_extraction(
                    name=name, description=description, image_paths=image_paths
                )
            else:
                logger.info("  [SKIP] No images. Stage 1 skipped.")
                # Fallback: create raw text from metadata description?
                raw_text = f"Product Name: {name}\nDescription: {description}"

            stage1_file = os.path.join(item_dir, "raw_extraction.md")
            with open(stage1_file, "w") as f:
                f.write(f"--- SOURCE: {item.product_link} ---\n")
                f.write(raw_text)
            logger.info(f"  => Stage 1 saved to {stage1_file}")

            # --- STAGE 2: STRUCTURED EXTRACTION (Groq) ---
            logger.info("  [Stage 2] Running Groq Llama-3.3-70b (JSON Extraction)...")
            if raw_text and len(raw_text) > 10:
                result_obj = run_groq_json_extraction(raw_text)

                # Save as JSON
                stage2_file = os.path.join(item_dir, "analysis_result.json")
                with open(stage2_file, "w") as f:
                    # Model dump using alias (camelCase)
                    json.dump(
                        result_obj.model_dump(by_alias=True, exclude_none=True),
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                logger.info(f"  => Stage 2 saved to {stage2_file}")

                # Check flavors for verification
                logger.info(f"     Flavors found: {result_obj.flavor_names}")
                logger.info(f"     Weight: {result_obj.weight_grams}g")
            else:
                logger.info("  [SKIP] Raw text too short/empty. Stage 2 skipped.")

        except Exception as e:
            logger.error(f"  [ERROR] {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_pipeline_full()
