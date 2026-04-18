"""Tests for deterministic helper functions used by Dagster assets."""

from unittest import TestCase
from unittest.mock import patch

from agents.acquisition import (
    SourcePageContext,
    build_download_result,
    build_prepared_extraction_inputs,
    extract_image_urls,
    load_scraper_context,
    resolve_fallback_reason,
)
from agents.defs.assets import build_extraction_handoff, build_handoff_metadata
from agents.extraction import (
    build_analysis_input,
    build_analysis_metadata,
    build_image_report_metadata,
    build_json_context_block,
    run_image_ocr_step,
)
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

    def test_extract_image_urls_filters_decorative_keywords(self):
        """Drops URLs whose path matches configured decorative keywords."""
        with patch.dict(
            "os.environ",
            {
                "AGENTS_IMAGE_FILTER_EXCLUDE_KEYWORDS": "caveira,logo",
            },
            clear=False,
        ):
            image_urls = extract_image_urls(
                scraper_context={
                    "images": [
                        {"imageUrl": "https://cdn.example.com/product.jpg"},
                        {"imageUrl": "https://cdn.example.com/caveira-brand.jpg"},
                    ],
                },
            )

        self.assertEqual(image_urls, ["https://cdn.example.com/product.jpg"])

    def test_extract_image_urls_dedupes_querystring_variants(self):
        """Treats querystring-only URL variants as the same image by default."""
        image_urls = extract_image_urls(
            scraper_context={
                "images": [
                    {"imageUrl": "https://cdn.example.com/product.jpg?v=1"},
                    {"imageUrl": "https://cdn.example.com/product.jpg?v=2"},
                ],
            },
        )

        self.assertEqual(image_urls, ["https://cdn.example.com/product.jpg?v=1"])

    def test_extract_image_urls_respects_max_images(self):
        """Caps image selection when the configured max is reached."""
        with patch.dict(
            "os.environ",
            {
                "AGENTS_IMAGE_FILTER_MAX_IMAGES": "2",
            },
            clear=False,
        ):
            image_urls = extract_image_urls(
                scraper_context={
                    "images": [
                        {"imageUrl": "https://cdn.example.com/a.jpg"},
                        {"imageUrl": "https://cdn.example.com/b.jpg"},
                        {"imageUrl": "https://cdn.example.com/c.jpg"},
                    ],
                },
            )

        self.assertEqual(
            image_urls,
            [
                "https://cdn.example.com/a.jpg",
                "https://cdn.example.com/b.jpg",
            ],
        )

    def test_load_scraper_context_rejects_invalid_json(self):
        """Invalid source context returns None instead of raising."""
        self.assertIsNone(load_scraper_context({"source_page_api_context": "nope"}))

    def test_resolve_fallback_reason(self):
        """Explains when image reporting will run without images."""
        self.assertEqual(resolve_fallback_reason(["https://cdn.example.com/a.jpg"]), "")
        self.assertEqual(resolve_fallback_reason([]), "no_images_available")


class TestExtractionHelpers(TestCase):
    """Tests for structured extraction helper behavior."""

    def test_build_json_context_block_limits_large_payloads(self):
        """Renders contextual JSON blocks for raw LLM extraction."""
        block = build_json_context_block("SCRAPER_CONTEXT", {"name": "x" * 8000})

        self.assertIn("[SCRAPER_CONTEXT (TRUNCATED)]", block)
        self.assertTrue(block.strip().endswith("[/SCRAPER_CONTEXT (TRUNCATED)]"))
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

    def test_run_image_ocr_step_keeps_image_order(self):
        """One OCR call still preserves the original image order in its output."""
        prepared = build_prepared_extraction_inputs(
            downloaded_assets={
                "origin_item_id": 10,
                "url": "https://example.com/p",
                "source_page_api_context": '{"product": {"name": "Whey"}}',
                "source_page_html_structured_data": (
                    '{"json-ld": [{"image": ["https://cdn.example.com/a.png", '
                    '"https://cdn.example.com/b.png"]}]}'
                ),
            },
        )

        with patch(
            "agents.extraction.run_image_report_extraction",
            return_value="## IMAGE_1\nIMAGE_A\n\n## IMAGE_2\nIMAGE_B",
        ) as mock_runner:
            ocr_text, metadata = run_image_ocr_step(prepared_inputs=prepared)

        self.assertEqual(metadata["images_processed"], 2)
        self.assertEqual(
            mock_runner.call_args.kwargs["image_urls"],
            ["https://cdn.example.com/a.png", "https://cdn.example.com/b.png"],
        )
        self.assertIn("[IMAGE_MANIFEST]", mock_runner.call_args.kwargs["description"])
        self.assertIn(
            "IMAGE_1: https://cdn.example.com/a.png",
            mock_runner.call_args.kwargs["description"],
        )
        self.assertIn(
            "IMAGE_2: https://cdn.example.com/b.png",
            mock_runner.call_args.kwargs["description"],
        )
        self.assertIn("## IMAGE_1", ocr_text)
        self.assertIn("IMAGE_A", ocr_text)
        self.assertIn("## IMAGE_2", ocr_text)
        self.assertIn("IMAGE_B", ocr_text)
        self.assertLess(ocr_text.index("IMAGE_A"), ocr_text.index("IMAGE_B"))

    def test_build_image_report_metadata_summarizes_selected_images(self):
        """Image-report metadata reflects the deterministic prepared inputs."""
        prepared = build_prepared_extraction_inputs(
            downloaded_assets={
                "origin_item_id": 10,
                "url": "https://example.com/p",
                "source_page_api_context": '{"product": {"name": "Whey"}}',
                "source_page_html_structured_data": (
                    '{"json-ld": [{"image": "https://cdn.example.com/a.png"}]}'
                ),
            },
        )

        metadata = build_image_report_metadata(prepared_inputs=prepared)

        self.assertEqual(metadata["images_used"], 1)
        self.assertTrue(metadata["scraper_context_included"])

    def test_build_analysis_input_wraps_context_and_image_report(self):
        """Structured extraction receives JSON context plus ordered image notes."""
        prepared = build_prepared_extraction_inputs(
            downloaded_assets={
                "origin_item_id": 10,
                "url": "https://example.com/p",
                "source_page_api_context": '{"product": {"name": "Whey"}}',
                "source_page_html_structured_data": (
                    '{"json-ld": [{"image": "https://cdn.example.com/a.png"}]}'
                ),
            },
        )

        analysis_input = build_analysis_input(
            prepared_inputs=prepared,
            image_report_text="## IMAGE_1\nOCR",
        )

        self.assertIn("[SCRAPER_CONTEXT]", analysis_input)
        self.assertIn("[ORDERED_IMAGE_OCR]", analysis_input)
        self.assertIn("## IMAGE_1", analysis_input)


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
            image_report="IMAGE REPORT",
        )

        self.assertEqual(handoff["originScrapedItemId"], 10)
        self.assertEqual(handoff["sourcePageId"], 20)
        self.assertEqual(handoff["product"]["name"], "Whey")
        self.assertEqual(handoff["imageReport"], "IMAGE REPORT")

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
