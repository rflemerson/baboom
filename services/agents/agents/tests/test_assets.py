from unittest import TestCase

from agents.acquisition.ingestion import (
    build_download_result,
    get_item_or_raise,
    resolve_source_page_context,
)
from agents.acquisition.metadata import build_metadata_extraction_context
from agents.acquisition.prepared_inputs import (
    load_scraper_context,
    resolve_extraction_mode,
)
from agents.contracts.acquisition import MetadataExtractionContext, SourcePageContext
from agents.contracts.publishing import PublishOriginContext
from agents.extraction.context_utils import count_invalid_variant_tokens
from agents.extraction.structured_analysis import (
    StructuredAnalysisResult,
    VariantExtractionContext,
    build_analysis_metadata,
)
from agents.publishing.payload_utils import (
    build_nutrition_payload,
    slugify,
    to_graphql_stock_status,
)
from agents.publishing.service import (
    build_component_payloads,
    build_product_store_payload,
    build_skipped_linked_result,
    build_tag_paths,
    build_upload_metadata,
    build_variant_external_id,
    resolve_analysis_items,
    should_skip_linked_item,
)
from agents.schemas.product import RawScrapedData


class _FakeCandidateStorage:
    """Small storage fake for prepared-input helper tests."""

    def __init__(self, *, site_data: str | None = None):
        self.site_data = site_data

    def exists(self, bucket: str, key: str) -> bool:
        if key == "site_data.json":
            return self.site_data is not None
        return False

    def download(self, bucket: str, key: str) -> str:
        if key != "site_data.json" or self.site_data is None:
            message = "unexpected download"
            raise AssertionError(message)
        return self.site_data


class TestAssetsHelpers(TestCase):
    """Tests for small helper functions used by Dagster assets."""

    def test_slugify(self):
        """Normalizes names to stable slugs."""
        self.assertEqual(slugify("Whey Protein 100%"), "whey-protein-100")
        self.assertEqual(slugify("###"), "item")

    def test_stock_status_mapping(self):
        """Maps scraper statuses to GraphQL enum values."""
        self.assertEqual(to_graphql_stock_status("A"), "AVAILABLE")
        self.assertEqual(to_graphql_stock_status("LAST_UNITS"), "LAST_UNITS")
        self.assertEqual(to_graphql_stock_status("unknown"), "AVAILABLE")

    def test_build_nutrition_payload(self):
        """Builds nutrition payload with converted numeric fields."""
        payload = build_nutrition_payload(
            {
                "variant_name": "Chocolate",
                "flavor_names": ["Chocolate"],
                "nutrition_facts": {
                    "serving_size_grams": 30,
                    "energy_kcal": 120,
                    "proteins": 20,
                    "carbohydrates": 4,
                    "total_sugars": 2,
                    "added_sugars": 0,
                    "total_fats": 2,
                    "saturated_fats": 1,
                    "trans_fats": 0,
                    "dietary_fiber": 1,
                    "sodium": 50,
                    "micronutrients": [
                        {"name": "vitamin-c", "value": 45, "unit": "mg"},
                    ],
                },
            },
        )

        self.assertEqual(len(payload), 1)
        facts = payload[0]["nutritionFacts"]
        self.assertEqual(facts["description"], "Chocolate")
        self.assertEqual(facts["energyKcal"], 120)
        self.assertEqual(payload[0]["flavorNames"], ["Chocolate"])


class _FakeApi:
    """Small test double for ingestion helper tests."""

    def __init__(self, item=None, ensured_item=None):
        self.item = item
        self.ensured_item = ensured_item

    def get_scraped_item(self, item_id: int):
        return self.item

    def ensure_source_page(self, item_id: int, url: str, store_slug: str):
        return self.ensured_item


class TestIngestionHelpers(TestCase):
    """Tests for small ingestion helper functions."""

    def test_get_item_or_raise_returns_item(self):
        item = {"id": 1, "name": "Item"}
        api = _FakeApi(item=item)
        self.assertEqual(get_item_or_raise(api, 1), item)

    def test_get_item_or_raise_raises_when_missing(self):
        api = _FakeApi(item=None)
        with self.assertRaisesRegex(RuntimeError, "Scraped item 7 not found"):
            get_item_or_raise(api, 7)

    def test_resolve_source_page_context_returns_normalized_payload(self):
        api = _FakeApi(
            item={"id": 1},
            ensured_item={
                "id": 1,
                "sourcePageId": 55,
                "sourcePageUrl": "https://example.com/p",
                "storeSlug": "demo-store",
            },
        )
        config = type(
            "Config",
            (),
            {"item_id": 1, "url": "https://fallback", "store_slug": "demo-store"},
        )()
        item = {
            "productLink": "https://example.com/p",
            "sourcePageRawContent": "<html></html>",
            "sourcePageContentType": "HTML",
        }

        page = resolve_source_page_context(api, config, item)

        self.assertEqual(page.page_id, 55)
        self.assertEqual(page.page_url, "https://example.com/p")
        self.assertEqual(page.store_slug, "demo-store")
        self.assertEqual(page.source_page_content_type, "HTML")

    def test_build_download_result_maps_source_page_context(self):
        page = SourcePageContext(
            item_id=1,
            page_id=55,
            page_url="https://example.com/p",
            store_slug="demo-store",
            source_page_raw_content="<html></html>",
            source_page_content_type="HTML",
        )

        result = build_download_result("55/source.html", page)

        self.assertEqual(result["origin_item_id"], 1)
        self.assertEqual(result["page_id"], 55)
        self.assertEqual(result["url"], "https://example.com/p")
        self.assertEqual(result["storage_path"], "55/source.html")


class TestAnalysisHelpers(TestCase):
    """Tests for small structured-analysis helper functions."""

    def test_count_context_invalid_variants_is_zero_without_allowed_variants(self):
        payload = {"items": [{"variant_name": "Chocolate"}]}
        self.assertEqual(count_invalid_variant_tokens(payload, set()), 0)

    def test_build_analysis_metadata_maps_structured_result(self):
        analysis = StructuredAnalysisResult(
            payload={"items": [{"name": "Whey"}]},
            variant_context=VariantExtractionContext(
                expected_variant_count=3,
                allowed_variants={"chocolate", "vanilla"},
            ),
            structured_variant_count=2,
            reconciliation_retry_used=True,
            context_guard_retry_used=False,
            context_invalid_variants=1,
        )

        metadata = build_analysis_metadata(
            analysis=analysis,
            started=0.0,
        )

        self.assertEqual(metadata["items_detected"], 1)
        self.assertEqual(metadata["variants_detected_raw"], 3)
        self.assertEqual(metadata["variants_detected_structured"], 2)
        self.assertTrue(metadata["reconciliation_retry_used"])
        self.assertFalse(metadata["context_guard_retry_used"])
        self.assertEqual(metadata["context_invalid_variants"], 1)
        self.assertIn("duration_ms", metadata)

    def test_variant_extraction_context_is_value_object(self):
        context = VariantExtractionContext(
            expected_variant_count=2,
            allowed_variants={"chocolate", "vanilla"},
        )
        self.assertEqual(context.expected_variant_count, 2)
        self.assertEqual(context.allowed_variants, {"chocolate", "vanilla"})


class TestMetadataHelpers(TestCase):
    """Tests for small metadata helper functions."""

    def test_build_metadata_extraction_context_normalizes_downloaded_assets(self):
        extraction = build_metadata_extraction_context(
            {
                "storage_path": "55/source.html",
                "url": "https://example.com/p",
                "store_slug": "demo-store",
                "origin_item_id": "42",
            },
        )

        self.assertEqual(
            extraction,
            MetadataExtractionContext(
                storage_path="55/source.html",
                page_url="https://example.com/p",
                store_slug="demo-store",
                origin_item_id=42,
            ),
        )

    def test_load_scraper_context_parses_json_payloads_only(self):
        context = load_scraper_context(
            {
                "source_page_raw_content": '{"variants":["Chocolate"]}',
                "source_page_content_type": "JSON",
            },
        )
        self.assertEqual(context, {"variants": ["Chocolate"]})

    def test_resolve_extraction_mode_prefers_multimodal_when_images_exist(self):
        mode, reason = resolve_extraction_mode([{"file": "image_1.jpg"}], ["1/a.jpg"])
        self.assertEqual(mode, "multimodal")
        self.assertEqual(reason, "")


class TestPublishHelpers(TestCase):
    """Tests for small publish helper functions."""

    def test_resolve_analysis_items_falls_back_to_scraped_metadata_name(self):
        items = resolve_analysis_items(
            product_analysis={"items": []},
            scraped_metadata=RawScrapedData(name="Fallback Product"),
            origin_item={"name": "Origin Product"},
        )

        self.assertEqual(items, [{"name": "Fallback Product"}])

    def test_should_skip_linked_item_only_when_product_store_exists(self):
        self.assertTrue(
            should_skip_linked_item(
                {"status": "linked", "productStoreId": 77},
            ),
        )
        self.assertFalse(
            should_skip_linked_item(
                {"status": "linked", "productStoreId": None},
            ),
        )

    def test_build_skipped_linked_result_keeps_linked_product_id(self):
        result = build_skipped_linked_result({"linkedProductId": 99})
        self.assertTrue(result["skipped"])
        self.assertEqual(result["product"]["id"], 99)

    def test_build_variant_external_id_uses_origin_context(self):
        origin = PublishOriginContext(
            item_id=1,
            page_id=55,
            page_url="https://example.com/p",
            store_slug="demo-store",
            item={"externalId": "origin-1"},
        )
        external_id = build_variant_external_id(
            origin,
            1,
            {"name": "Whey Protein", "variant_name": "Chocolate"},
            RawScrapedData(name="Whey Protein"),
        )
        self.assertIn("origin-1::v2-", external_id)
        self.assertIn("whey-protein", external_id)

    def test_build_product_store_payload_prefers_scraped_metadata(self):
        payload = build_product_store_payload(
            scraped_metadata=RawScrapedData(price=99.9, stock_status="A"),
            origin_item={"price": 88.0, "stockStatus": "LAST_UNITS"},
            scraped_item={"externalId": "ext-1"},
            page_url="https://example.com/p",
            origin_store_slug="demo-store",
        )

        self.assertEqual(payload["storeName"], "demo-store")
        self.assertEqual(payload["productLink"], "https://example.com/p")
        self.assertEqual(payload["price"], 99.9)
        self.assertEqual(payload["externalId"], "ext-1")
        self.assertEqual(payload["stockStatus"], "AVAILABLE")

    def test_build_tag_paths_filters_empty_values(self):
        payload = build_tag_paths(["protein/whey", "", None, "goal/gain-mass"])
        self.assertEqual(
            payload,
            [{"path": "protein/whey"}, {"path": "goal/gain-mass"}],
        )

    def test_build_component_payloads_filters_unnamed_components(self):
        payload = build_component_payloads(
            [
                {"name": "Dose", "quantity": "2 units", "weight_hint": "30g"},
                {"name": ""},
                {"quantity": 1},
            ],
        )

        self.assertEqual(
            payload,
            [
                {
                    "name": "Dose",
                    "quantity": 2,
                    "weightHint": "30g",
                    "packagingHint": None,
                },
            ],
        )

    def test_build_upload_metadata_summarizes_publish_result(self):
        metadata = build_upload_metadata(
            results=[{"product": {"id": 1}}, {"product": {"id": 2}}],
            created_count=1,
            page_id=55,
            started=0.0,
        )

        self.assertEqual(metadata["items_uploaded"], 2)
        self.assertEqual(metadata["additional_scraped_items_created"], 1)
        self.assertEqual(metadata["page_id"], 55)
        self.assertIn("duration_ms", metadata)
