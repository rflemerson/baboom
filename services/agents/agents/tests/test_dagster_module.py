"""Tests for Dagster sensor/assets behavior in the agents module."""

from unittest import TestCase
from unittest.mock import patch

from dagster import RunRequest, SkipReason, build_asset_context

from agents.acquisition import PreparedExtractionInputs
from agents.definitions import defs
from agents.defs.assets import (
    downloaded_assets,
    extraction_handoff,
    image_report,
    product_analysis,
)
from agents.defs.pipeline import (
    ItemConfig,
    QueueWorkItem,
    build_item_run_config,
    build_item_run_request,
)
from agents.defs.sensors import work_queue_sensor
from agents.schemas import ExtractedProduct


class _FakeApiClient:
    """Simple API client spy for sensor/assets tests."""

    def __init__(self, work_payload=None):
        self.work_payload = work_payload
        self.report_error_calls: list[tuple[int, str, bool]] = []
        self._items: dict[int, dict] = {}
        self._next_page_id = 5000

    def seed_item(self, item_id: int, payload: dict) -> dict:
        """Insert one fake scraped item for tests."""
        item = {
            "id": int(item_id),
            "name": payload["name"],
            "status": payload.get("status", "processing"),
            "storeSlug": payload["store_slug"],
            "storeName": payload["store_slug"].replace("_", " ").title(),
            "externalId": payload["external_id"],
            "price": payload.get("price"),
            "stockStatus": payload.get("stock_status"),
            "productLink": payload.get("page_url"),
            "sourcePageUrl": payload.get("page_url"),
            "sourcePageId": payload.get("source_page_id"),
            "sourcePageApiContext": payload.get("source_page_api_context", ""),
            "sourcePageHtmlStructuredData": payload.get(
                "source_page_html_structured_data",
                "",
            ),
            "productStoreId": payload.get("product_store_id"),
            "linkedProductId": payload.get("linked_product_id"),
        }
        self._items[int(item_id)] = item
        return item

    def checkout_work(self):
        """Return configured queue payload."""
        return self.work_payload

    def report_error(self, item_id, message, is_fatal=False):
        """Track reported errors."""
        self.report_error_calls.append((int(item_id), str(message), bool(is_fatal)))

    def get_scraped_item(self, item_id: int):
        """Return fake scraped item payload by id."""
        return self._items.get(int(item_id))

    def ensure_source_page(self, item_id: int, url: str, store_slug: str):
        """Ensure source page fields are present in fake item."""
        item = self._items.get(int(item_id))
        if not item:
            return None
        if not item.get("sourcePageId"):
            item["sourcePageId"] = self._next_page_id
            self._next_page_id += 1
        item["sourcePageUrl"] = item.get("sourcePageUrl") or url
        item["productLink"] = item.get("productLink") or item["sourcePageUrl"]
        item["storeSlug"] = store_slug or item.get("storeSlug")
        item["storeName"] = item["storeSlug"].replace("_", " ").title()
        return item


class TestDagsterSensor(TestCase):
    """Tests for work queue Dagster sensor logic."""

    def test_definitions_validate_loadable(self):
        """The Dagster code location remains structurally loadable."""
        type(defs).validate_loadable(defs)

    def test_sensor_skips_when_queue_empty(self):
        """Returns SkipReason when checkout has no pending item."""
        api = _FakeApiClient(work_payload=None)
        with patch("agents.defs.sensors.AgentClient", return_value=api):
            results = list(work_queue_sensor(context=None))
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], SkipReason)

    def test_sensor_skips_when_item_has_no_url(self):
        """Returns SkipReason if item payload has no URL fields."""
        api = _FakeApiClient(work_payload={"id": 11})
        with patch("agents.defs.sensors.AgentClient", return_value=api):
            results = list(work_queue_sensor(context=None))
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], SkipReason)

    def test_sensor_yields_runrequest_with_expected_ops(self):
        """Yields run config with Dagster assets wired for one item."""
        api = _FakeApiClient(
            work_payload={
                "id": 22,
                "productLink": "https://example.com/p",
                "storeSlug": "demo-store",
                "storeName": "Demo Store",
            },
        )
        with patch("agents.defs.sensors.AgentClient", return_value=api):
            results = list(work_queue_sensor(context=None))
        self.assertEqual(len(results), 1)
        run = results[0]
        self.assertIsInstance(run, RunRequest)
        self.assertEqual(run.run_key, "22")
        self.assertEqual(run.tags["item_id"], "22")
        ops = run.run_config["ops"]
        self.assertIn("downloaded_assets", ops)
        self.assertEqual(list(ops), ["downloaded_assets"])

    def test_build_item_run_request_uses_shared_config(self):
        """Builds stable run config for queued items."""
        item = QueueWorkItem(
            item_id=7,
            url="https://example.com/p",
            store_name="Demo",
            store_slug="demo",
        )
        request = build_item_run_request(item)
        self.assertEqual(request.run_key, "7")
        self.assertEqual(request.run_config, build_item_run_config(item))


class TestDagsterAssets(TestCase):
    """Tests for asset adapters around deterministic helpers."""

    def test_downloaded_assets_normalizes_api_context(self):
        """Loads the item, ensures source page, and emits normalized context."""
        api = _FakeApiClient()
        api.seed_item(
            99,
            {
                "name": "Demo Product",
                "store_slug": "demo-store",
                "external_id": "sku-99",
                "page_url": "https://example.com/product",
                "source_page_id": 123,
                "source_page_api_context": '{"items": []}',
                "source_page_html_structured_data": '{"json-ld": []}',
            },
        )

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = downloaded_assets(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=99,
                    url="https://example.com/product",
                    store_slug="demo-store",
                ),
            )

        self.assertEqual(result["origin_item_id"], 99)
        self.assertEqual(result["page_id"], 123)
        self.assertEqual(result["store_slug"], "demo-store")
        self.assertEqual(result["source_page_api_context"], '{"items": []}')

    def test_image_report_reports_errors(self):
        """Reports image-report errors against the origin item."""
        api = _FakeApiClient()
        prepared_inputs = PreparedExtractionInputs(
            origin_item_id=99,
            page_url="https://example.com/product",
            scraper_context={},
            image_urls=[],
            fallback_reason="no_images_found",
        )

        with (
            patch("agents.defs.assets.AgentClient", return_value=api),
            patch(
                "agents.defs.assets.run_image_report_step",
                side_effect=RuntimeError("boom"),
            ),
            self.assertRaisesRegex(RuntimeError, "boom"),
        ):
            image_report(
                context=build_asset_context(),
                prepared_extraction_inputs=prepared_inputs,
            )

        self.assertEqual(len(api.report_error_calls), 1)
        self.assertEqual(api.report_error_calls[0][0], 99)

    def test_product_analysis_returns_single_product_tree(self):
        """Structured analysis returns one root product dict."""
        product = ExtractedProduct(
            name="Combo",
            children=[ExtractedProduct(name="Creatina")],
        )
        prepared_inputs = PreparedExtractionInputs(
            origin_item_id=99,
            page_url="https://example.com/product",
            scraper_context={"product": {"name": "Combo"}},
            image_urls=[],
            fallback_reason="",
        )

        with patch("agents.defs.assets.run_analysis_pipeline", return_value=product):
            result = product_analysis(
                context=build_asset_context(),
                prepared_extraction_inputs=prepared_inputs,
                image_report="IMAGE REPORT",
            )

        self.assertEqual(result["name"], "Combo")
        self.assertEqual(result["children"][0]["name"], "Creatina")

    def test_extraction_handoff_emits_payload_without_api_writes(self):
        """The final asset no longer creates catalog products."""
        result = extraction_handoff(
            context=build_asset_context(),
            product_analysis={"name": "Whey", "children": []},
            image_report="IMAGE REPORT",
            downloaded_assets={
                "origin_item_id": 99,
                "page_id": 123,
                "url": "https://example.com/product",
                "store_slug": "demo-store",
            },
        )

        self.assertEqual(result["originScrapedItemId"], 99)
        self.assertEqual(result["product"]["name"], "Whey")
        self.assertEqual(result["imageReport"], "IMAGE REPORT")
