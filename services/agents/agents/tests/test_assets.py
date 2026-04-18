"""Tests for deterministic helper functions used by Dagster assets."""

from unittest import TestCase

from agents.acquisition import (
    SourcePageContext,
    build_download_result,
    build_prepared_extraction_inputs,
    extract_image_urls,
    load_scraper_context,
    resolve_fallback_reason,
)
from agents.defs.assets import build_extraction_handoff, build_handoff_metadata
from agents.extraction import build_analysis_metadata, build_json_context_block
from agents.schemas import ExtractedProduct, NutritionFacts


class TestAcquisitionHelpers(TestCase):
    """Tests for deterministic source-page preparation."""

    def test_build_download_result_preserves_source_context(self):
        """Builds the payload consumed by downstream extraction assets."""
        result = build_download_result(
            SourcePageContext(
                item_id=10,
                page_id=20,
                page_url="https://example.com/p",
                store_slug="demo",
                source_page_api_context='{"product": {"name": "Whey"}}',
                source_page_html_structured_data='{"json-ld": []}',
            ),
        )

        self.assertEqual(result["origin_item_id"], 10)
        self.assertEqual(result["page_id"], 20)
        self.assertEqual(result["store_slug"], "demo")
        self.assertIn("source_page_api_context", result)

    def test_build_prepared_extraction_inputs_uses_api_and_html_images(self):
        """Extracts ordered image URLs from both deterministic contexts."""
        prepared = build_prepared_extraction_inputs(
            downloaded_assets={
                "origin_item_id": 10,
                "url": "https://example.com/p",
                "source_page_api_context": (
                    '{"items": [{"images": [{"imageUrl": '
                    '"https://cdn.example.com/a.jpg"}]}]}'
                ),
                "source_page_html_structured_data": (
                    '{"json-ld": [{"image": "https://cdn.example.com/b.png"}]}'
                ),
            },
        )

        self.assertEqual(
            prepared.image_urls,
            ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.png"],
        )
        self.assertEqual(prepared.fallback_reason, "")

    def test_extract_image_urls_ignores_structured_data_vocabulary_urls(self):
        """Does not treat schema vocabulary URLs as product images."""
        image_urls = extract_image_urls(
            scraper_context=None,
            html_structured_data={
                "rdfa": [
                    {"image": "https://ogp.me/ns"},
                    {"image": "https://cdn.example.com/product.webp"},
                ],
            },
        )

        self.assertEqual(image_urls, ["https://cdn.example.com/product.webp"])

    def test_load_scraper_context_rejects_invalid_json(self):
        """Invalid source context returns None instead of raising."""
        self.assertIsNone(load_scraper_context({"source_page_api_context": "nope"}))

    def test_resolve_fallback_reason(self):
        """Explains when raw extraction will run without images."""
        self.assertEqual(resolve_fallback_reason(["https://cdn.example.com/a.jpg"]), "")
        self.assertEqual(resolve_fallback_reason([]), "no_images_available")


class TestExtractionHelpers(TestCase):
    """Tests for structured extraction helper behavior."""

    def test_build_json_context_block_limits_large_payloads(self):
        """Renders contextual JSON blocks for raw LLM extraction."""
        block = build_json_context_block("SCRAPER_CONTEXT", {"name": "x" * 8000})

        self.assertIn("[SCRAPER_CONTEXT]", block)
        self.assertTrue(block.endswith("[/SCRAPER_CONTEXT]"))
        self.assertIn("...", block)

    def test_build_analysis_metadata_counts_recursive_children(self):
        """Summarizes one extracted product tree."""
        product = ExtractedProduct(
            name="Combo",
            children=[
                ExtractedProduct(name="Whey"),
                ExtractedProduct(name="Creatina"),
            ],
        )

        metadata = build_analysis_metadata(product=product, started=0.0)

        self.assertEqual(metadata["root_product_name"], "Combo")
        self.assertEqual(metadata["children_detected"], 2)
        self.assertEqual(metadata["total_product_nodes"], 3)

    def test_extracted_product_accepts_recursive_children_and_nutrition(self):
        """The single output schema represents simple products and combos."""
        product = ExtractedProduct(
            name="Combo",
            nutrition_facts=NutritionFacts(
                serving_size_grams=30,
                energy_kcal=120,
                proteins=24,
                carbohydrates=3,
                total_fats=2,
            ),
            children=[ExtractedProduct(name="Creatina", weight_grams=500)],
        )

        payload = product.model_dump()

        self.assertEqual(payload["name"], "Combo")
        self.assertEqual(payload["children"][0]["name"], "Creatina")
        self.assertEqual(payload["nutrition_facts"]["proteins"], 24)


class TestPublishingHelpers(TestCase):
    """Tests for the final extraction handoff payload."""

    def test_build_extraction_handoff_keeps_product_tree_and_source_ids(self):
        """Builds the final payload without deciding catalog writes."""
        handoff = build_extraction_handoff(
            product={"name": "Whey", "children": []},
            downloaded_assets={
                "origin_item_id": 10,
                "page_id": 20,
                "url": "https://example.com/p",
                "store_slug": "demo",
            },
            raw_extraction="RAW",
        )

        self.assertEqual(handoff["originScrapedItemId"], 10)
        self.assertEqual(handoff["sourcePageId"], 20)
        self.assertEqual(handoff["product"]["name"], "Whey")
        self.assertEqual(handoff["rawExtraction"], "RAW")

    def test_build_handoff_metadata_summarizes_payload(self):
        """Builds asset metadata for the handoff asset."""
        metadata = build_handoff_metadata(
            handoff={
                "originScrapedItemId": 10,
                "sourcePageId": 20,
                "product": {"name": "Combo", "children": [{"name": "Whey"}]},
            },
            started=0.0,
        )

        self.assertEqual(metadata["origin_item_id"], 10)
        self.assertEqual(metadata["source_page_id"], 20)
        self.assertEqual(metadata["root_product_name"], "Combo")
        self.assertEqual(metadata["children_detected"], 1)
