"""Tests for Dagster sensor/assets behavior in the agents module."""

from unittest import TestCase
from unittest.mock import patch

from dagster import RunRequest, SkipReason, build_asset_context

from agents.acquisition import PreparedExtractionInputs
from agents.definitions import defs
from agents.defs.assets import (
    downloaded_assets,
    product_analysis,
    raw_extraction,
    upload_to_api,
)
from agents.defs.pipeline import (
    PROCESS_ITEM_JOB_NAME,
    ItemConfig,
    QueueWorkItem,
    build_item_run_config,
    build_item_run_request,
)
from agents.defs.sensors import work_queue_sensor
from agents.schemas import ProductAnalysisList, ProductAnalysisResult


class _FakeApiClient:
    """Simple API client spy for sensor/assets tests."""

    def __init__(self, work_payload=None, create_raises: Exception | None = None):
        self.work_payload = work_payload
        self.create_raises = create_raises
        self.report_error_calls: list[tuple[int, str, bool]] = []
        self.create_calls: list[dict] = []
        self._items: dict[int, dict] = {}
        self._next_item_id = 1000
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
            "sourcePageRawContent": payload.get("source_page_raw_content", ""),
            "sourcePageContentType": payload.get("source_page_content_type", ""),
            "productStoreId": payload.get("product_store_id"),
            "linkedProductId": payload.get("linked_product_id"),
        }
        self._items[int(item_id)] = item
        self._next_item_id = max(self._next_item_id, int(item_id) + 1)
        source_page_id = payload.get("source_page_id")
        if source_page_id is not None:
            self._next_page_id = max(self._next_page_id, int(source_page_id) + 1)
        return item

    def checkout_work(self):
        """Return configured queue payload."""
        return self.work_payload

    def create_product(self, payload):
        """Simulate API create product behavior."""
        self.create_calls.append(payload)
        if self.create_raises:
            raise self.create_raises
        return {"product": {"id": 1}, "errors": []}

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

    def update_scraped_item_data(
        self,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ):
        """Update mutable fields in fake item and return payload."""
        item = self._items.get(int(item_id))
        if not item:
            return None
        if name:
            item["name"] = name
        if store_slug:
            item["storeSlug"] = store_slug
            item["storeName"] = store_slug.replace("_", " ").title()
        if source_page_url:
            item["sourcePageUrl"] = source_page_url
            item["productLink"] = source_page_url
            if not item.get("sourcePageId"):
                item["sourcePageId"] = self._next_page_id
                self._next_page_id += 1
        return item

    def upsert_scraped_item_variant(
        self,
        origin_item_id: int,
        external_id: str,
        name: str,
        page_url: str,
        store_slug: str,
        price: float | None = None,
        stock_status: str | None = None,
    ):
        """Create or update one variant item in memory."""
        origin = self._items.get(int(origin_item_id))
        if not origin:
            return None

        existing = None
        for item in self._items.values():
            if (
                item.get("storeSlug") == store_slug
                and item.get("externalId") == external_id
            ):
                existing = item
                break

        if existing is None:
            item_id = self._next_item_id
            self._next_item_id += 1
            existing = {
                "id": item_id,
                "name": name,
                "status": "processing",
                "storeSlug": store_slug,
                "storeName": store_slug.replace("_", " ").title(),
                "externalId": external_id,
                "price": price if price is not None else origin.get("price"),
                "stockStatus": stock_status or origin.get("stockStatus"),
                "productLink": page_url,
                "sourcePageUrl": page_url,
                "sourcePageId": origin.get("sourcePageId") or self._next_page_id,
                "sourcePageRawContent": "",
                "sourcePageContentType": "",
                "productStoreId": None,
                "linkedProductId": None,
            }
            self._items[item_id] = existing
        else:
            existing["name"] = name
            existing["price"] = price if price is not None else existing.get("price")
            existing["stockStatus"] = stock_status or existing.get("stockStatus")
            existing["sourcePageUrl"] = page_url
            existing["productLink"] = page_url
        return existing


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
        self.assertIn("product_analysis", ops)
        self.assertIn("upload_to_api", ops)
        self.assertEqual(ops["downloaded_assets"]["config"]["item_id"], 22)
        self.assertEqual(
            ops["downloaded_assets"]["config"]["url"],
            "https://example.com/p",
        )


class TestDagsterPipelineContract(TestCase):
    """Tests for the shared Dagster pipeline contract."""

    def test_build_item_run_request_uses_shared_job_payload(self):
        """Run request is built from the normalized queue item contract."""
        item = QueueWorkItem(
            item_id=33,
            url="https://example.com/item",
            store_name="Example Store",
            store_slug="example-store",
        )

        run_request = build_item_run_request(item)
        run_config = build_item_run_config(item)

        self.assertIsInstance(run_request, RunRequest)
        self.assertEqual(run_request.run_key, "33")
        self.assertEqual(run_request.tags["store"], "Example Store")
        self.assertEqual(run_request.run_config, run_config)
        self.assertEqual(
            run_config["ops"]["downloaded_assets"]["config"]["store_slug"],
            "example-store",
        )

    def test_process_item_job_name_stays_stable(self):
        """Shared process item job name stays in one central location."""
        self.assertEqual(PROCESS_ITEM_JOB_NAME, "process_item_job")


class TestUploadToApiErrorHandling(TestCase):
    """Tests for upload asset error reporting behavior."""

    def test_upload_reports_error_when_create_product_fails(self):
        """Asset must report queue error and re-raise upload exceptions."""
        api = _FakeApiClient(create_raises=RuntimeError("create failed"))
        api.seed_item(
            101,
            {
                "name": "Demo Product",
                "store_slug": "demo-store",
                "external_id": "demo-1",
                "page_url": "https://example.com/product",
                "source_page_id": 10,
                "status": "processing",
                "price": 99.9,
                "stock_status": "A",
            },
        )

        with (
            self.assertRaises(RuntimeError),
            patch("agents.defs.assets.AgentClient", return_value=api),
        ):
            _ = upload_to_api(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=101,
                    url="https://example.com/product",
                    store_slug="demo-store",
                ),
                product_analysis={
                    "items": [{"name": "Demo Product", "packaging": "CONTAINER"}],
                },
                downloaded_assets={"origin_item_id": 101},
            )

        self.assertEqual(len(api.report_error_calls), 1)
        reported_item_id, _message, is_fatal = api.report_error_calls[0]
        self.assertEqual(reported_item_id, 101)
        self.assertFalse(is_fatal)


class TestDagsterAssetsFlow(TestCase):
    """Tests for asset functions not covered by sensor/upload-error tests."""

    def test_downloaded_assets_sets_source_page_when_missing(self):
        """Creates source_page and returns expected storage context payload."""
        api = _FakeApiClient()
        api.seed_item(
            1,
            {
                "name": "Item",
                "store_slug": "demo-store",
                "external_id": "item-1",
                "page_url": "https://example.com/p1",
                "status": "new",
            },
        )
        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = downloaded_assets(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=1,
                    url="https://example.com/p1",
                    store_slug="demo-store",
                ),
            )

        seeded = api.get_scraped_item(1)
        self.assertIsNotNone(seeded["sourcePageId"])
        self.assertEqual(result["origin_item_id"], 1)
        self.assertEqual(result["page_id"], seeded["sourcePageId"])

    @patch(
        "agents.defs.assets.run_raw_extraction_step",
        return_value=("RAW-TEXT", {"images_used": 2}),
    )
    def test_raw_extraction_uses_candidates_manifest(self, mock_raw):
        """Selects image URLs from scraper context and forwards them to raw extraction."""
        prepared = PreparedExtractionInputs(
            origin_item_id=1,
            page_url="https://x",
            scraper_context={
                "platform": "shopify",
                "variants": [{"title": "Chocolate"}],
            },
            image_urls=[
                "https://cdn.example.com/a.jpg",
                "https://cdn.example.com/b.jpg",
            ],
            fallback_reason="",
        )
        with patch(
            "agents.defs.assets.AgentClient",
            return_value=_FakeApiClient(),
        ):
            result = raw_extraction(
                context=build_asset_context(),
                prepared_extraction_inputs=prepared,
            )

        self.assertEqual(result, "RAW-TEXT")
        call_kwargs = mock_raw.call_args.kwargs
        forwarded_inputs = call_kwargs["prepared_inputs"]
        self.assertEqual(forwarded_inputs.page_url, "https://x")
        self.assertEqual(len(forwarded_inputs.image_urls), 2)
        self.assertEqual(
            forwarded_inputs.image_urls[0],
            "https://cdn.example.com/a.jpg",
        )
        self.assertEqual(
            forwarded_inputs.scraper_context,
            {"platform": "shopify", "variants": [{"title": "Chocolate"}]},
        )

    @patch(
        "agents.defs.assets.run_raw_extraction_step",
        return_value=("RAW-TEXT", {"images_used": 0}),
    )
    def test_raw_extraction_falls_back_to_text_only_when_no_candidates(self, mock_raw):
        """Falls back to text-only extraction when no candidates are available."""
        prepared = PreparedExtractionInputs(
            origin_item_id=1,
            page_url="https://x",
            scraper_context=None,
            image_urls=[],
            fallback_reason="no_images_available",
        )
        with patch(
            "agents.defs.assets.AgentClient",
            return_value=_FakeApiClient(),
        ):
            result = raw_extraction(
                context=build_asset_context(),
                prepared_extraction_inputs=prepared,
            )

        self.assertEqual(result, "RAW-TEXT")
        self.assertEqual(mock_raw.call_args.kwargs["prepared_inputs"].image_urls, [])

    @patch("agents.defs.assets.run_structured_extraction")
    def test_product_analysis_reports_error_on_failure(self, mock_structured):
        """Reports queue error when structured extraction raises."""
        mock_structured.side_effect = RuntimeError("structured failed")
        api = _FakeApiClient()

        with (
            self.assertRaisesRegex(RuntimeError, "structured failed"),
            patch("agents.defs.assets.AgentClient", return_value=api),
        ):
            product_analysis(
                context=build_asset_context(),
                config=ItemConfig(item_id=99, url="https://x", store_slug="demo"),
                raw_extraction="RAW",
            )

        self.assertEqual(len(api.report_error_calls), 1)
        self.assertEqual(api.report_error_calls[0][0], 99)

    @patch("agents.defs.assets.run_structured_extraction")
    def test_product_analysis_retries_when_raw_has_more_variants(self, mock_structured):
        """Retries structured extraction when OCR indicates more variants than output."""
        mock_structured.side_effect = [
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Elitebar",
                        flavor_names=["Peanut"],
                        variant_name="Peanut",
                        is_variant=True,
                    ),
                ],
            ),
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Elitebar",
                        flavor_names=["Peanut"],
                        variant_name="Peanut",
                        is_variant=True,
                    ),
                    ProductAnalysisResult(
                        name="Elitebar",
                        flavor_names=["Cookies & Cream"],
                        variant_name="Cookies & Cream",
                        is_variant=True,
                    ),
                ],
            ),
        ]
        api = _FakeApiClient()
        raw_text = "### 4. AVAILABLE FLAVORS\n- Peanut\n- Cookies & Cream\n- Coco\n"

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = product_analysis(
                context=build_asset_context(),
                config=ItemConfig(item_id=91, url="https://x", store_slug="demo"),
                raw_extraction=raw_text,
            )

        self.assertEqual(mock_structured.call_count, 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][1]["variant_name"], "Cookies & Cream")

    @patch("agents.defs.assets.run_structured_extraction")
    def test_product_analysis_skips_retry_when_consistent(self, mock_structured):
        """Keeps single structured call when variant count is already consistent."""
        mock_structured.return_value = ProductAnalysisList(
            items=[
                ProductAnalysisResult(
                    name="Product",
                    flavor_names=["Chocolate", "Vanilla"],
                    variant_name="Chocolate",
                    is_variant=True,
                ),
                ProductAnalysisResult(
                    name="Product",
                    flavor_names=["Vanilla"],
                    variant_name="Vanilla",
                    is_variant=True,
                ),
            ],
        )
        api = _FakeApiClient()
        raw_text = "### 4. AVAILABLE FLAVORS\n- Chocolate\n- Vanilla\n"

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = product_analysis(
                context=build_asset_context(),
                config=ItemConfig(item_id=92, url="https://x", store_slug="demo"),
                raw_extraction=raw_text,
            )

        self.assertEqual(mock_structured.call_count, 1)
        self.assertEqual(len(result["items"]), 2)

    @patch("agents.defs.assets.run_structured_extraction")
    def test_product_analysis_retries_when_flavor_outside_context(
        self,
        mock_structured,
    ):
        """Retries with context guard when extracted flavor is not allowed."""
        mock_structured.side_effect = [
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Product",
                        flavor_names=["Strawberry"],
                        variant_name="Strawberry",
                        is_variant=True,
                    ),
                ],
            ),
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Product",
                        flavor_names=["Chocolate"],
                        variant_name="Chocolate",
                        is_variant=True,
                    ),
                ],
            ),
        ]
        api = _FakeApiClient()
        raw_text = (
            "[SCRAPER_CONTEXT]\n"
            '{"platform":"shopify","options":[{"name":"Flavor","values":["Chocolate"]}]}\n'
            "[/SCRAPER_CONTEXT]"
        )

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = product_analysis(
                context=build_asset_context(),
                config=ItemConfig(item_id=94, url="https://x", store_slug="demo"),
                raw_extraction=raw_text,
            )

        self.assertEqual(mock_structured.call_count, 2)
        self.assertEqual(result["items"][0]["variant_name"], "Chocolate")
        self.assertIn(
            "Allowed variants",
            mock_structured.call_args_list[1].kwargs["prompt"],
        )

    @patch("agents.defs.assets.run_structured_extraction")
    def test_product_analysis_retries_when_variant_outside_scraper_context(
        self,
        mock_structured,
    ):
        """Retries when structured flavor is not present in scraper context variants."""
        mock_structured.side_effect = [
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Product",
                        flavor_names=["Strawberry"],
                        variant_name="Strawberry",
                        is_variant=True,
                    ),
                ],
            ),
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Product",
                        flavor_names=["Chocolate"],
                        variant_name="Chocolate",
                        is_variant=True,
                    ),
                ],
            ),
        ]
        api = _FakeApiClient()
        raw_text = (
            "[SCRAPER_CONTEXT]\n"
            '{"platform":"shopify","options":[{"name":"Flavor","values":["Chocolate","Vanilla"]}]}\n'
            "[/SCRAPER_CONTEXT]"
        )

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = product_analysis(
                context=build_asset_context(),
                config=ItemConfig(item_id=95, url="https://x", store_slug="demo"),
                raw_extraction=raw_text,
            )

        self.assertEqual(mock_structured.call_count, 2)
        self.assertEqual(result["items"][0]["variant_name"], "Chocolate")
        self.assertIn(
            "Allowed variants",
            mock_structured.call_args_list[1].kwargs["prompt"],
        )

    def test_upload_to_api_creates_additional_variant_items(self):
        """Creates extra scraped items when analysis returns multiple items."""
        api = _FakeApiClient()
        api.seed_item(
            201,
            {
                "name": "Origin",
                "store_slug": "demo-store",
                "external_id": "demo-origin",
                "page_url": "https://example.com/product",
                "source_page_id": 44,
                "status": "processing",
                "price": 90,
                "stock_status": "A",
            },
        )

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = upload_to_api(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=201,
                    url="https://example.com/product",
                    store_slug="demo-store",
                ),
                product_analysis={
                    "items": [
                        {"name": "Base Product", "packaging": "CONTAINER"},
                        {
                            "name": "Base Product",
                            "variant_name": "Chocolate",
                            "packaging": "CONTAINER",
                        },
                    ],
                },
                downloaded_assets={"origin_item_id": 201},
            )

        self.assertEqual(len(result), 2)
        self.assertEqual(len(api.create_calls), 2)
        self.assertTrue(
            any("::v2-" in str(item.get("externalId")) for item in api._items.values()),
        )

    def test_upload_to_api_skips_already_linked_item(self):
        """Skips create_product when scraped item is already linked."""
        api = _FakeApiClient()
        api.seed_item(
            301,
            {
                "name": "Linked",
                "store_slug": "demo-store",
                "external_id": "demo-linked",
                "page_url": "https://example.com/already-linked",
                "source_page_id": 55,
                "status": "linked",
                "price": 90,
                "stock_status": "A",
                "product_store_id": 77,
                "linked_product_id": 99,
            },
        )

        with patch("agents.defs.assets.AgentClient", return_value=api):
            result = upload_to_api(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=301,
                    url="https://example.com/already-linked",
                    store_slug="demo-store",
                ),
                product_analysis={
                    "items": [{"name": "Linked", "packaging": "CONTAINER"}],
                },
                downloaded_assets={"origin_item_id": 301},
            )

        self.assertEqual(len(api.create_calls), 0)
        self.assertTrue(result[0]["skipped"])

    def test_upload_to_api_handles_numeric_strings_from_llm_payload(self):
        """Parses numeric strings in analysis payload without crashing."""
        api = _FakeApiClient()
        api.seed_item(
            401,
            {
                "name": "Origin Num",
                "store_slug": "demo-store",
                "external_id": "demo-origin-num",
                "page_url": "https://example.com/product-numeric",
                "source_page_id": 66,
                "status": "processing",
                "price": 90,
                "stock_status": "A",
            },
        )

        with patch("agents.defs.assets.AgentClient", return_value=api):
            _ = upload_to_api(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=401,
                    url="https://example.com/product-numeric",
                    store_slug="demo-store",
                ),
                product_analysis={
                    "items": [
                        {
                            "name": "Numeric Product",
                            "brand_name": "Growth",
                            "packaging": "CONTAINER",
                            "weight_grams": "900g",
                            "components": [
                                {
                                    "name": "Dose",
                                    "weight_grams": "30g",
                                    "brand_name": "Growth",
                                    "category_hierarchy": ["Protein", "Dose"],
                                    "quantity": "2 units",
                                    "ean": "7891234567890",
                                    "description": "Dose do combo",
                                    "packaging": "REFILL",
                                    "tags_hierarchy": [["Goal", "Mass"]],
                                    "nutrition_facts": {
                                        "serving_size_grams": "30g",
                                        "energy_kcal": "120 kcal",
                                        "proteins": "24g",
                                        "carbohydrates": "3g",
                                        "total_fats": "2g",
                                    },
                                },
                            ],
                            "nutrition_facts": {
                                "serving_size_grams": "30g",
                                "energy_kcal": "120 kcal",
                                "proteins": "24g",
                                "carbohydrates": "3g",
                                "total_sugars": "1,5g",
                                "added_sugars": "0g",
                                "total_fats": "2g",
                                "saturated_fats": "0.5g",
                                "trans_fats": "0g",
                                "dietary_fiber": "1g",
                                "sodium": "150mg",
                                "micronutrients": [
                                    {"name": "Vitamin C", "value": "45mg"},
                                ],
                            },
                        },
                    ],
                },
                downloaded_assets={"origin_item_id": 401},
            )

        self.assertTrue(api.create_calls)
        payload = api.create_calls[0]
        self.assertEqual(payload["weight"], 900)
        self.assertEqual(payload["originScrapedItemId"], 401)
        self.assertEqual(payload["stores"][0]["price"], 90.0)
        self.assertEqual(payload["components"][0]["quantity"], 2)
        self.assertEqual(payload["components"][0]["weight"], 30)
        self.assertEqual(payload["components"][0]["brandName"], "Growth")
        self.assertEqual(payload["components"][0]["categoryPath"], ["Protein", "Dose"])
        self.assertEqual(payload["components"][0]["packaging"], "REFILL")
        self.assertTrue(payload["components"][0]["nutrition"])
        self.assertNotIn("nutrientClaims", payload)
        self.assertEqual(
            payload["nutrition"][0]["nutritionFacts"]["servingSizeGrams"],
            30.0,
        )
        self.assertEqual(payload["nutrition"][0]["nutritionFacts"]["energyKcal"], 120)
        self.assertEqual(payload["nutrition"][0]["nutritionFacts"]["totalSugars"], 1.5)
