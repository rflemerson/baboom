"""Tests for Dagster sensor/assets behavior in the agents module."""

from unittest import TestCase
from unittest.mock import patch

from dagster import RunRequest, SkipReason, build_asset_context

from agents.definitions import defs
from agents.defs.assets import (
    ItemConfig,
    _is_potential_table_candidate,
    _select_images_for_ocr,
    downloaded_assets,
    ocr_extraction,
    product_analysis,
    scraped_metadata,
    upload_to_api,
)
from agents.defs.pipeline import (
    PROCESS_ITEM_JOB_NAME,
    QueueWorkItem,
    build_item_run_config,
    build_item_run_request,
)
from agents.defs.sensors import work_queue_sensor
from agents.schemas.analysis import ProductAnalysisList, ProductAnalysisResult
from agents.schemas.product import RawScrapedData


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


class _FakeClientResource:
    """Fake Dagster resource wrapper for AgentClientResource."""

    def __init__(self, api):
        self.api = api

    def get_client(self):
        """Return fake client."""
        return self.api


class TestDagsterSensor(TestCase):
    """Tests for work queue Dagster sensor logic."""

    def test_definitions_validate_loadable(self):
        """The Dagster code location remains structurally loadable."""
        defs.validate_loadable()

    def test_sensor_skips_when_queue_empty(self):
        """Returns SkipReason when checkout has no pending item."""
        api = _FakeApiClient(work_payload=None)
        results = list(work_queue_sensor(context=None, client=_FakeClientResource(api)))
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], SkipReason)

    def test_sensor_skips_when_item_has_no_url(self):
        """Returns SkipReason if item payload has no URL fields."""
        api = _FakeApiClient(work_payload={"id": 11})
        results = list(work_queue_sensor(context=None, client=_FakeClientResource(api)))
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
        results = list(work_queue_sensor(context=None, client=_FakeClientResource(api)))
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


class TestImageSelection(TestCase):
    """Tests for OCR image selection strategy."""

    @patch.dict(
        "os.environ",
        {
            "OCR_MAX_IMAGES": "4",
            "OCR_MAX_NUTRITION_IMAGES": "2",
            "OCR_MAX_IMAGES_NO_NUTRITION": "6",
        },
        clear=False,
    )
    def test_selection_prioritizes_nutrition_and_completes_with_context(self):
        """Keeps nutrition-like images first, then fills with highest score."""
        candidates = [
            {"file": "images/a.jpg", "score": 40, "nutrition_signal": 0},
            {"file": "images/b.jpg", "score": 20, "nutrition_signal": 4},
            {"file": "images/c.jpg", "score": 30, "nutrition_signal": 2},
            {"file": "images/d.jpg", "score": 50, "nutrition_signal": 0},
            {"file": "images/e.jpg", "score": 10, "nutrition_signal": 0},
        ]
        selected = _select_images_for_ocr(candidates, "77")
        self.assertEqual(len(selected), 4)
        self.assertEqual(selected[0], "77/images/b.jpg")
        self.assertEqual(selected[1], "77/images/c.jpg")
        self.assertIn("77/images/d.jpg", selected)

    @patch.dict(
        "os.environ",
        {
            "OCR_MAX_IMAGES": "4",
            "OCR_MAX_NUTRITION_IMAGES": "2",
            "OCR_MAX_IMAGES_NO_NUTRITION": "6",
        },
        clear=False,
    )
    def test_selection_uses_fallback_limit_without_nutrition_signal(self):
        """Uses broader fallback cap when no nutrition clue exists."""
        candidates = [
            {"file": f"images/{idx}.jpg", "score": 100 - idx, "nutrition_signal": 0}
            for idx in range(8)
        ]
        selected = _select_images_for_ocr(candidates, "88")
        self.assertEqual(len(selected), 6)
        self.assertEqual(selected[0], "88/images/0.jpg")

    @patch.dict(
        "os.environ",
        {
            "OCR_MAX_IMAGES": "4",
            "OCR_MAX_NUTRITION_IMAGES": "10",
            "OCR_MAX_IMAGES_NO_NUTRITION": "6",
            "OCR_INCLUDE_ALL_TABLES": "0",
        },
        clear=False,
    )
    def test_selection_caps_nutrition_quota_to_total_limit(self):
        """Never exceeds total limit even if nutrition quota is misconfigured."""
        candidates = [
            {"file": f"images/{idx}.jpg", "score": 100 - idx, "nutrition_signal": 3}
            for idx in range(8)
        ]
        selected = _select_images_for_ocr(candidates, "99")
        self.assertEqual(len(selected), 4)

    @patch.dict(
        "os.environ",
        {
            "OCR_MAX_IMAGES": "4",
            "OCR_MAX_NUTRITION_IMAGES": "10",
            "OCR_MAX_IMAGES_NO_NUTRITION": "6",
            "OCR_INCLUDE_ALL_TABLES": "1",
        },
        clear=False,
    )
    def test_selection_can_keep_all_table_candidates_in_high_recall_mode(self):
        """High recall mode can exceed base cap to avoid losing nutrition tables."""
        candidates = [
            {"file": f"images/{idx}.jpg", "score": 100 - idx, "nutrition_signal": 3}
            for idx in range(8)
        ]
        selected = _select_images_for_ocr(candidates, "99")
        self.assertGreaterEqual(len(selected), 8)

    @patch.dict(
        "os.environ",
        {
            "OCR_MAX_IMAGES": "6",
            "OCR_MAX_NUTRITION_IMAGES": "6",
            "OCR_MAX_IMAGES_NO_NUTRITION": "6",
        },
        clear=False,
    )
    def test_selection_filters_mixed_catalog_by_target_product(self):
        """Keeps OCR focused on target product when page has related products."""
        candidates = [
            {
                "file": "images/whey.jpg",
                "score": 50,
                "nutrition_signal": 2,
                "url": "https://cdn/x/whey.jpg",
                "metadata": {"alt": "Whey Protein 1kg Soldiers Nutrition"},
            },
            {
                "file": "images/elite-1.jpg",
                "score": 30,
                "nutrition_signal": 2,
                "url": "https://cdn/x/elitebar-chocolate.jpg",
                "metadata": {"alt": "Elitebar 30g Protein Bar"},
            },
            {
                "file": "images/elite-2.jpg",
                "score": 25,
                "nutrition_signal": 2,
                "url": "https://cdn/x/elitebar-cookies.jpg",
                "metadata": {"alt": "Elitebar 30g Protein Bar"},
            },
        ]
        selected = _select_images_for_ocr(
            candidates,
            "9002",
            product_name="Elitebar 30g Protein Bar",
            page_url="https://soldiersnutrition.com.br/products/elitebar-30g-barra-de-proteina-soldiers-nutrition",
        )
        self.assertEqual(
            selected,
            ["9002/images/elite-1.jpg", "9002/images/elite-2.jpg"],
        )

    @patch.dict(
        "os.environ",
        {
            "OCR_MAX_IMAGES": "4",
            "OCR_MAX_NUTRITION_IMAGES": "4",
            "OCR_MAX_IMAGES_NO_NUTRITION": "4",
        },
        clear=False,
    )
    def test_selection_fallbacks_when_no_product_match_exists(self):
        """Falls back to score-based selection if no product token matches."""
        candidates = [
            {"file": "images/a.jpg", "score": 20, "nutrition_signal": 1},
            {"file": "images/b.jpg", "score": 10, "nutrition_signal": 1},
        ]
        selected = _select_images_for_ocr(
            candidates,
            "12",
            product_name="Missing Product",
            page_url="https://example.com/products/missing-product",
        )
        self.assertEqual(selected, ["12/images/a.jpg", "12/images/b.jpg"])

    @patch.dict("os.environ", {"OCR_CV_TABLE_THRESHOLD": "0.2"}, clear=False)
    def test_potential_table_candidate_accepts_high_cv_score(self):
        """Accepts table candidate using CV score even without keyword hints."""
        candidate = {
            "file": "images/cv.jpg",
            "score": 2,
            "nutrition_signal": 0,
            "cv_table_score": 0.9,
            "metadata": {"alt": "product image"},
            "url": "https://cdn/x/image.jpg",
        }
        self.assertTrue(_is_potential_table_candidate(candidate))


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

        with self.assertRaises(RuntimeError):
            _ = upload_to_api(
                context=build_asset_context(),
                config=ItemConfig(
                    item_id=101,
                    url="https://example.com/product",
                    store_slug="demo-store",
                ),
                client=_FakeClientResource(api),
                product_analysis={
                    "items": [{"name": "Demo Product", "packaging": "CONTAINER"}],
                },
                scraped_metadata=RawScrapedData(
                    name="Demo Product",
                    brand_name="Demo Brand",
                    description="Description",
                    price=99.9,
                    stock_status="A",
                ),
            )

        self.assertEqual(len(api.report_error_calls), 1)
        reported_item_id, _message, is_fatal = api.report_error_calls[0]
        self.assertEqual(reported_item_id, 101)
        self.assertFalse(is_fatal)


class _FakeScraperService:
    """Test double for scraper resource methods."""

    def __init__(self):
        self.extract_metadata_result: dict = {"opengraph": []}
        self.consolidate_result = RawScrapedData(name="N", brand_name="B")
        self.extract_raises: Exception | None = None
        self.download_assets_calls: list[tuple[int, str]] = []
        self.materialize_calls: list[tuple[str, str]] = []

    def download_assets(self, item_id: int, url: str):
        """Track download call and return storage path."""
        self.download_assets_calls.append((item_id, url))
        return f"{item_id}/source.html"

    def extract_metadata(self, _storage_path: str, _url: str):
        """Return metadata or raise configured exception."""
        if self.extract_raises:
            raise self.extract_raises
        return self.extract_metadata_result

    def materialize_candidates(self, bucket: str, page_url: str):
        """Track candidate materialization requests."""
        self.materialize_calls.append((bucket, page_url))
        return []

    def consolidate(self, _meta: dict, brand_name_override: str):
        """Return configured consolidated structure."""
        return RawScrapedData(
            name=self.consolidate_result.name,
            brand_name=brand_name_override,
            description=self.consolidate_result.description,
        )


class _FakeScraperResource:
    """Resource wrapper returning fake scraper service."""

    def __init__(self, service):
        self.service = service

    def get_service(self):
        """Return fake service."""
        return self.service


class _FakeStorage:
    """Storage test double for OCR asset."""

    def __init__(self, data: dict[str, bytes]):
        self.data = data

    def exists(self, bucket: str, key: str) -> bool:
        """Check if key exists in fake storage map."""
        return f"{bucket}/{key}" in self.data

    def download(self, bucket: str, key: str):
        """Download bytes from fake storage map."""
        return self.data[f"{bucket}/{key}"]


class _FakeStorageResource:
    """Resource wrapper returning fake storage."""

    def __init__(self, storage):
        self.storage = storage

    def get_storage(self):
        """Return fake storage."""
        return self.storage


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
        scraper = _FakeScraperService()
        result = downloaded_assets(
            context=build_asset_context(),
            config=ItemConfig(
                item_id=1,
                url="https://example.com/p1",
                store_slug="demo-store",
            ),
            scraper=_FakeScraperResource(scraper),
            client=_FakeClientResource(api),
        )

        seeded = api.get_scraped_item(1)
        self.assertIsNotNone(seeded["sourcePageId"])
        self.assertEqual(result["origin_item_id"], 1)
        self.assertEqual(
            result["storage_path"],
            f"{seeded['sourcePageId']}/source.html",
        )

    def test_scraped_metadata_reports_error_on_extraction_failure(self):
        """Reports queue error when metadata extraction fails."""
        api = _FakeApiClient()
        scraper = _FakeScraperService()
        scraper.extract_raises = RuntimeError("meta failed")

        with self.assertRaisesRegex(RuntimeError, "meta failed"):
            scraped_metadata(
                context=build_asset_context(),
                scraper=_FakeScraperResource(scraper),
                client=_FakeClientResource(api),
                downloaded_assets={
                    "storage_path": "10/source.html",
                    "url": "https://example.com/p",
                    "store_slug": "demo-store",
                    "origin_item_id": 10,
                },
            )

        self.assertEqual(len(api.report_error_calls), 1)
        self.assertEqual(api.report_error_calls[0][0], 10)

    @patch("agents.defs.assets.ocr.run_raw_extraction", return_value="RAW-TEXT")
    def test_ocr_extraction_uses_candidates_manifest(self, mock_raw):
        """Selects image paths from candidates and forwards them to raw extraction."""
        candidates = (
            b'[{"file":"images/a.jpg","score":10,"nutrition_signal":3,"metadata":{"alt":"Nutrition table flavor chocolate"}},'
            b' {"file":"images/b.jpg","score":8,"nutrition_signal":0,"metadata":{"alt":"Product flavor chocolate"}}]'
        )
        storage = _FakeStorage(
            {
                "15/candidates.json": candidates,
                "15/site_data.json": b'{"page_url":"https://x","extracted":{"json-ld":[]}}',
            },
        )
        result = ocr_extraction(
            context=build_asset_context(),
            scraper=_FakeScraperResource(_FakeScraperService()),
            storage=_FakeStorageResource(storage),
            client=_FakeClientResource(_FakeApiClient()),
            scraped_metadata=RawScrapedData(
                name="Product",
                brand_name="Brand",
                description="Desc",
            ),
            downloaded_assets={
                "origin_item_id": 1,
                "url": "https://x",
                "storage_path": "15/source.html",
                "source_page_raw_content": '{"platform":"shopify","variants":[{"title":"Chocolate"}]}',
                "source_page_content_type": "JSON",
            },
        )

        self.assertEqual(result, "RAW-TEXT")
        call_kwargs = mock_raw.call_args.kwargs
        self.assertEqual(call_kwargs["name"], "Product")
        self.assertEqual(len(call_kwargs["image_paths"]), 2)
        self.assertEqual(call_kwargs["image_paths"][0], "15/images/a.jpg")
        self.assertIn("[IMAGE_SEQUENCE_CONTEXT]", call_kwargs["description"])
        self.assertIn("[SITE_DATA]", call_kwargs["description"])
        self.assertIn("[SCRAPER_CONTEXT]", call_kwargs["description"])
        self.assertIn("kind=NUTRITION_TABLE", call_kwargs["description"])
        self.assertIn("kind=PRODUCT_IMAGE", call_kwargs["description"])

    @patch("agents.defs.assets.ocr.run_raw_extraction", return_value="RAW-TEXT")
    def test_ocr_extraction_falls_back_to_text_only_when_no_candidates(self, mock_raw):
        """Falls back to text-only extraction when no candidates are available."""
        result = ocr_extraction(
            context=build_asset_context(),
            scraper=_FakeScraperResource(_FakeScraperService()),
            storage=_FakeStorageResource(_FakeStorage({})),
            client=_FakeClientResource(_FakeApiClient()),
            scraped_metadata=RawScrapedData(
                name="Product",
                brand_name="Brand",
                description="Desc",
            ),
            downloaded_assets={
                "origin_item_id": 1,
                "url": "https://x",
                "storage_path": "15/source.html",
            },
        )

        self.assertEqual(result, "RAW-TEXT")
        self.assertEqual(mock_raw.call_args.kwargs["image_paths"], [])

    @patch("agents.defs.assets.analysis.run_structured_extraction")
    def test_product_analysis_reports_error_on_failure(self, mock_structured):
        """Reports queue error when structured extraction raises."""
        mock_structured.side_effect = RuntimeError("structured failed")
        api = _FakeApiClient()

        with self.assertRaisesRegex(RuntimeError, "structured failed"):
            product_analysis(
                context=build_asset_context(),
                config=ItemConfig(item_id=99, url="https://x", store_slug="demo"),
                client=_FakeClientResource(api),
                ocr_extraction="RAW",
            )

        self.assertEqual(len(api.report_error_calls), 1)
        self.assertEqual(api.report_error_calls[0][0], 99)

    @patch("agents.defs.assets.analysis.run_structured_extraction")
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

        result = product_analysis(
            context=build_asset_context(),
            config=ItemConfig(item_id=91, url="https://x", store_slug="demo"),
            client=_FakeClientResource(api),
            ocr_extraction=raw_text,
        )

        self.assertEqual(mock_structured.call_count, 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][1]["variant_name"], "Cookies & Cream")

    @patch("agents.defs.assets.analysis.run_structured_extraction")
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

        result = product_analysis(
            context=build_asset_context(),
            config=ItemConfig(item_id=92, url="https://x", store_slug="demo"),
            client=_FakeClientResource(api),
            ocr_extraction=raw_text,
        )

        self.assertEqual(mock_structured.call_count, 1)
        self.assertEqual(len(result["items"]), 2)

    @patch("agents.defs.assets.analysis.run_structured_extraction")
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

        result = product_analysis(
            context=build_asset_context(),
            config=ItemConfig(item_id=94, url="https://x", store_slug="demo"),
            client=_FakeClientResource(api),
            ocr_extraction=raw_text,
        )

        self.assertEqual(mock_structured.call_count, 2)
        self.assertEqual(result["items"][0]["variant_name"], "Chocolate")
        self.assertIn(
            "Allowed variants",
            mock_structured.call_args_list[1].kwargs["prompt"],
        )

    @patch("agents.defs.assets.analysis.run_structured_extraction")
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

        result = product_analysis(
            context=build_asset_context(),
            config=ItemConfig(item_id=95, url="https://x", store_slug="demo"),
            client=_FakeClientResource(api),
            ocr_extraction=raw_text,
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

        result = upload_to_api(
            context=build_asset_context(),
            config=ItemConfig(
                item_id=201,
                url="https://example.com/product",
                store_slug="demo-store",
            ),
            client=_FakeClientResource(api),
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
            scraped_metadata=RawScrapedData(
                name="Base Product",
                brand_name="Brand",
                description="Desc",
                price=90,
                stock_status="A",
            ),
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

        result = upload_to_api(
            context=build_asset_context(),
            config=ItemConfig(
                item_id=301,
                url="https://example.com/already-linked",
                store_slug="demo-store",
            ),
            client=_FakeClientResource(api),
            product_analysis={"items": [{"name": "Linked", "packaging": "CONTAINER"}]},
            scraped_metadata=RawScrapedData(
                name="Linked",
                brand_name="Brand",
                description="Desc",
                price=90,
                stock_status="A",
            ),
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

        _ = upload_to_api(
            context=build_asset_context(),
            config=ItemConfig(
                item_id=401,
                url="https://example.com/product-numeric",
                store_slug="demo-store",
            ),
            client=_FakeClientResource(api),
            product_analysis={
                "items": [
                    {
                        "name": "Numeric Product",
                        "packaging": "CONTAINER",
                        "weight_grams": "900g",
                        "components": [{"name": "Dose", "quantity": "2 units"}],
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
                            "micronutrients": [{"name": "Vitamin C", "value": "45mg"}],
                        },
                    },
                ],
            },
            scraped_metadata=RawScrapedData(
                name="Numeric Product",
                brand_name="Brand",
                description="Desc",
                price=99.9,
                stock_status="A",
            ),
        )

        self.assertTrue(api.create_calls)
        payload = api.create_calls[0]
        self.assertEqual(payload["weight"], 900)
        self.assertEqual(payload["stores"][0]["price"], 99.9)
        self.assertEqual(payload["components"][0]["quantity"], 2)
        self.assertEqual(
            payload["nutrition"][0]["nutritionFacts"]["servingSizeGrams"],
            30.0,
        )
        self.assertEqual(payload["nutrition"][0]["nutritionFacts"]["energyKcal"], 120)
        self.assertEqual(payload["nutrition"][0]["nutritionFacts"]["totalSugars"], 1.5)
