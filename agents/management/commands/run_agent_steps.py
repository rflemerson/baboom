"""Management command to manually run agent pipeline steps."""

import json
import logging
import os

from django.core.management.base import BaseCommand

from agents.brain.groq_agent import run_groq_json_extraction
from agents.brain.raw_extraction_agent import run_raw_extraction
from agents.storage import get_storage
from agents.tools.scraper import ScraperService
from scrapers.models import ScrapedItem

# Configure logging
logger = logging.getLogger(__name__)


def get_item_dir(item_id):
    """Get temp directory for item."""
    path = f"temp/{item_id}"
    os.makedirs(path, exist_ok=True)
    return path


class Command(BaseCommand):
    """Run specific agent pipeline steps manually."""

    help = "Run specific agent pipeline steps for an item"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument("item_id", type=int, help="ScrapedItem ID to test")
        parser.add_argument(
            "step",
            choices=["download", "metadata", "images", "raw", "structured", "full"],
            help="Step to run",
        )

    def handle(self, *args, **options):
        """Handle command execution."""
        item_id = options["item_id"]
        step = options["step"]

        if step == "download":
            self.step_download(item_id)
        elif step == "metadata":
            self.step_metadata(item_id)
        elif step == "images":
            self.step_images(item_id)
        elif step == "raw":
            self.step_raw(item_id)
        elif step == "structured":
            self.step_structured(item_id)
        elif step == "full":
            self.step_download(item_id)
            self.step_metadata(item_id)
            self.step_images(item_id)
            self.step_raw(item_id)
            self.step_structured(item_id)

    def step_download(self, item_id):
        """Run step 1: Download assets."""
        self.stdout.write(
            f"--- STEP 1: DOWNLOAD & ASSET MIRRORING (Item {item_id}) ---"
        )
        try:
            item = ScrapedItem.objects.get(id=item_id)
        except ScrapedItem.DoesNotExist:
            self.stderr.write(f"Item {item_id} not found")
            return

        service = ScraperService()

        # This downloads to the configured storage and returns the base path
        storage_base = service.download_assets(item.id, item.product_link)

        # Mirroring to local temp/ id for visibility
        item_dir = get_item_dir(item_id)
        storage = get_storage()
        bucket, _ = storage_base.split("/", 1)

        html_key = "source.html"
        if storage.exists(bucket, html_key):
            content = storage.download(bucket, html_key)
            with open(os.path.join(item_dir, "source.html"), "wb") as f:
                f.write(content)

        meta_key = "data.json"
        if storage.exists(bucket, meta_key):
            content = storage.download(bucket, meta_key)
            with open(os.path.join(item_dir, "extracted_metadata.json"), "wb") as f:
                f.write(content)

        cand_key = "candidates.json"
        if storage.exists(bucket, cand_key):
            content = storage.download(bucket, cand_key)
            with open(os.path.join(item_dir, "candidates.json"), "wb") as f:
                f.write(content)

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

        self.stdout.write(f"Assets mirrored to {item_dir}")

    def step_metadata(self, item_id):
        """Run step 2: Extract metadata."""
        self.stdout.write(f"--- STEP 2: METADATA EXTRACTION (Item {item_id}) ---")
        item_dir = get_item_dir(item_id)
        cand_path = os.path.join(item_dir, "candidates.json")
        meta_path = os.path.join(item_dir, "extracted_metadata.json")

        if not os.path.exists(cand_path) or not os.path.exists(meta_path):
            self.stderr.write("Run 'download' step first.")
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

        self.stdout.write(f"Consolidated metadata saved to {cons_path}")
        self.stdout.write(f"Name: {result.name}")
        self.stdout.write(f"EAN: {result.ean}")

    def step_images(self, item_id):
        """Run step 3: Filter images."""
        self.stdout.write(
            f"--- STEP 3: IMAGE FILTERING & SELECTION (Item {item_id}) ---"
        )
        item_dir = get_item_dir(item_id)
        cand_path = os.path.join(item_dir, "candidates.json")

        if not os.path.exists(cand_path):
            self.stderr.write("Run 'download' step first.")
            return

        with open(cand_path) as f:
            candidates = json.load(f)

        valid = [c for c in candidates if c["score"] > 0]
        valid.sort(key=lambda x: x["score"], reverse=True)

        self.stdout.write(f"Found {len(candidates)} total images.")
        self.stdout.write(f"After filtering (SVG, Size), {len(valid)} images remain.")

        for i, c in enumerate(valid[:10]):
            self.stdout.write(f"  #{i + 1}: {c['file']} (Score: {c['score']})")

    def step_raw(self, item_id):
        """Run step 4: Raw extraction with Gemma."""
        self.stdout.write(f"--- STEP 4: RAW EXTRACTION - GEMMA 3 (Item {item_id}) ---")
        item_dir = get_item_dir(item_id)
        cons_path = os.path.join(item_dir, "consolidated_scraped.json")
        cand_path = os.path.join(item_dir, "candidates.json")

        if not os.path.exists(cons_path) or not os.path.exists(cand_path):
            self.stderr.write("Run steps 'download' and 'metadata' first.")
            return

        with open(cons_path) as f:
            raw_data_dict = json.load(f)

        with open(cand_path) as f:
            candidates = json.load(f)

        valid = [c for c in candidates if c["score"] > 0]
        valid.sort(key=lambda x: x["score"], reverse=True)

        image_paths = [f"{item_id}/{c['file']}" for c in valid[:10]]

        self.stdout.write(f"Submitting {len(image_paths)} images to Gemma...")
        raw_text = run_raw_extraction(
            name=raw_data_dict["name"],
            description=raw_data_dict.get("description", ""),
            image_paths=image_paths,
        )

        output_path = os.path.join(item_dir, "raw_extraction.md")
        with open(output_path, "w") as f:
            f.write(raw_text)

        self.stdout.write(f"Raw Markdown saved to {output_path}")

    def step_structured(self, item_id):
        """Run step 5: Structured extraction with Groq."""
        self.stdout.write(
            f"--- STEP 5: STRUCTURED EXTRACTION - GROQ (Item {item_id}) ---"
        )
        item_dir = get_item_dir(item_id)
        raw_path = os.path.join(item_dir, "raw_extraction.md")

        if not os.path.exists(raw_path):
            self.stderr.write("Run step 'raw' first.")
            return

        with open(raw_path) as f:
            raw_text = f.read()

        self.stdout.write("Submitting raw text to Groq...")
        result_obj = run_groq_json_extraction(raw_text)

        output_path = os.path.join(item_dir, "analysis_result.json")
        with open(output_path, "w") as f:
            f.write(result_obj.model_dump_json(indent=2))

        self.stdout.write(f"Final JSON saved to {output_path}")
        self.stdout.write(f"Category Hierarchy: {result_obj.category_hierarchy}")
