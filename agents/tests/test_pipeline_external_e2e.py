"""Optional external E2E test for real scraper + LLM pipeline flow."""

import json
import os
from unittest import skipUnless

from django.test import SimpleTestCase

from agents.brain.raw_extraction_agent import run_raw_extraction
from agents.brain.structured_agent import run_structured_extraction
from agents.defs.assets.shared import _select_images_for_ocr
from agents.tools.scraper import ScraperService


def _has_llm_credentials() -> bool:
    """Check if env contains credentials for the configured LLM provider."""
    model = (os.getenv("LLM_MODEL") or "").strip().lower()
    if model.startswith(("gemini:", "google-gla:")):
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    if model.startswith("groq:"):
        return bool(os.getenv("GROQ_API_KEY"))
    if model.startswith("openai:"):
        return bool(os.getenv("OPENAI_API_KEY"))

    # Default: accept any configured provider key.
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GROQ_API_KEY")
    )


@skipUnless(
    os.getenv("RUN_EXTERNAL_PIPELINE_TESTS") == "1" and _has_llm_credentials(),
    "External pipeline test is opt-in. Set RUN_EXTERNAL_PIPELINE_TESTS=1 and provider API key env vars.",
)
class ExternalPipelineE2ETests(SimpleTestCase):
    """Runs one real URL through scraper manifest/cv and LLM extraction."""

    def test_real_url_pipeline_flow(self):
        """Executes real scraping + CV selection + LLM extraction on one URL."""
        url = os.getenv(
            "PIPELINE_TEST_URL",
            "https://soldiersnutrition.com.br/products/elitebar-30g-barra-de-proteina-soldiers-nutrition",
        )
        service = ScraperService()
        page_id = int(os.getenv("PIPELINE_TEST_ITEM_ID", "99001"))

        storage_path = service.download_assets(page_id, url)
        bucket, _ = storage_path.split("/", 1)

        metadata = service.extract_metadata(storage_path, url)
        scraped = service.consolidate(metadata)
        self.assertTrue(scraped.name or scraped.description)

        candidates = service.materialize_candidates(bucket, url)
        self.assertGreater(len(candidates), 0)
        image_paths = _select_images_for_ocr(
            candidates, bucket, product_name=scraped.name or "", page_url=url
        )
        self.assertGreater(len(image_paths), 0)

        raw_text = run_raw_extraction(
            name=scraped.name or url,
            description=scraped.description or "",
            image_paths=image_paths,
        )
        self.assertTrue(raw_text.strip())

        structured = run_structured_extraction(raw_text)
        payload = structured.model_dump(by_alias=True)
        self.assertIn("items", payload)
        self.assertIsInstance(payload["items"], list)
        self.assertGreater(len(payload["items"]), 0)

        # Smoke assertion for observability: payload must be serializable.
        json.dumps(payload, ensure_ascii=False)
