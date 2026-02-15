"""Tests for Dagster sensor/assets behavior in the agents module."""

from unittest.mock import patch

from dagster import RunRequest, SkipReason, build_asset_context
from django.test import SimpleTestCase, TestCase

from agents.assets import (
    ItemConfig,
    _is_potential_table_candidate,
    _select_images_for_ocr,
    downloaded_assets,
    ocr_extraction,
    product_analysis,
    scraped_metadata,
    upload_to_api,
)
from agents.schemas.analysis import ProductAnalysisList, ProductAnalysisResult
from agents.schemas.product import RawScrapedData
from agents.sensors import work_queue_sensor
from core.models import Brand, Product, ProductStore, Store
from scrapers.models import ScrapedItem, ScrapedPage


class _FakeApiClient:
    """Simple API client spy for sensor/assets tests."""

    def __init__(self, work_payload=None, create_raises: Exception | None = None):
        self.work_payload = work_payload
        self.create_raises = create_raises
        self.report_error_calls: list[tuple[int, str, bool]] = []
        self.create_calls: list[dict] = []

    @staticmethod
    def _serialize_item(item: ScrapedItem) -> dict:
        """Build GraphQL-like payload for one scraped item."""
        product_link = item.source_page.url if item.source_page else None
        linked_product_id = (
            item.product_store.product_id
            if item.product_store_id and item.product_store
            else None
        )
        return {
            "id": item.id,
            "name": item.name,
            "status": item.status,
            "storeSlug": item.store_slug,
            "storeName": item.store_slug.replace("_", " ").title(),
            "externalId": item.external_id,
            "price": item.price,
            "stockStatus": item.stock_status,
            "productLink": product_link,
            "sourcePageUrl": product_link,
            "sourcePageId": item.source_page_id,
            "productStoreId": item.product_store_id,
            "linkedProductId": linked_product_id,
        }

    def checkout_work(self):
        """Return configured queue payload."""
        return self.work_payload

    def create_product(self, _payload):
        """Simulate API create product behavior."""
        self.create_calls.append(_payload)
        if self.create_raises:
            raise self.create_raises
        return {"product": {"id": 1}, "errors": []}

    def report_error(self, item_id, message, is_fatal=False):
        """Track reported errors."""
        self.report_error_calls.append((int(item_id), str(message), bool(is_fatal)))

    def get_scraped_item(self, item_id: int):
        """Fetch item from DB and return GraphQL-like payload."""
        item = ScrapedItem.objects.filter(id=int(item_id)).first()
        if not item:
            return None
        return self._serialize_item(item)

    def ensure_source_page(self, item_id: int, url: str, store_slug: str):
        """Ensure source page exists and is attached to the item."""
        item = ScrapedItem.objects.filter(id=int(item_id)).first()
        if not item:
            return None
        if not item.source_page_id:
            page, _ = ScrapedPage.objects.get_or_create(
                store_slug=store_slug,
                url=url,
            )
            item.source_page = page
            item.store_slug = store_slug or item.store_slug
            item.save(update_fields=["source_page", "store_slug"])
        return self._serialize_item(item)

    def update_scraped_item_data(
        self,
        item_id: int,
        name: str | None = None,
        source_page_url: str | None = None,
        store_slug: str | None = None,
    ):
        """Update mutable fields in DB and return GraphQL-like payload."""
        item = ScrapedItem.objects.filter(id=int(item_id)).first()
        if not item:
            return None
        dirty_fields: list[str] = []
        if name:
            item.name = name
            dirty_fields.append("name")
        if store_slug:
            item.store_slug = store_slug
            dirty_fields.append("store_slug")
        if source_page_url:
            page, _ = ScrapedPage.objects.get_or_create(
                store_slug=item.store_slug,
                url=source_page_url,
            )
            item.source_page = page
            dirty_fields.append("source_page")
        if dirty_fields:
            item.save(update_fields=dirty_fields)
        return self._serialize_item(item)

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
        """Create or update one variant item in DB."""
        origin = ScrapedItem.objects.filter(id=int(origin_item_id)).first()
        if not origin:
            return None

        page = origin.source_page
        if not page:
            page, _ = ScrapedPage.objects.get_or_create(
                store_slug=store_slug, url=page_url
            )

        item, _ = ScrapedItem.objects.update_or_create(
            store_slug=store_slug,
            external_id=external_id,
            defaults={
                "name": name,
                "source_page": page,
                "status": ScrapedItem.Status.PROCESSING,
                "price": price if price is not None else origin.price,
                "stock_status": stock_status or origin.stock_status,
            },
        )
        return self._serialize_item(item)


class _FakeClientResource:
    """Fake Dagster resource wrapper for AgentClientResource."""

    def __init__(self, api):
        self.api = api

    def get_client(self):
        """Return fake client."""
        return self.api


class TestDagsterSensor(SimpleTestCase):
    """Tests for work queue Dagster sensor logic."""

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
            }
        )
        results = list(work_queue_sensor(context=None, client=_FakeClientResource(api)))
        self.assertEqual(len(results), 1)
        run = results[0]
        self.assertIsInstance(run, RunRequest)
        self.assertEqual(run.tags["item_id"], "22")
        ops = run.run_config["ops"]
        self.assertIn("downloaded_assets", ops)
        self.assertIn("product_analysis", ops)
        self.assertIn("upload_to_api", ops)
        self.assertEqual(ops["downloaded_assets"]["config"]["item_id"], 22)
        self.assertEqual(
            ops["downloaded_assets"]["config"]["url"], "https://example.com/p"
        )


class TestImageSelection(SimpleTestCase):
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
                "metadata": {"alt": "Elitebar 30g Barra De Proteína"},
            },
            {
                "file": "images/elite-2.jpg",
                "score": 25,
                "nutrition_signal": 2,
                "url": "https://cdn/x/elitebar-cookies.jpg",
                "metadata": {"alt": "Elitebar 30g Barra De Proteína"},
            },
        ]
        selected = _select_images_for_ocr(
            candidates,
            "9002",
            product_name="Elitebar 30g Barra De Proteína",
            page_url="https://soldiersnutrition.com.br/products/elitebar-30g-barra-de-proteina-soldiers-nutrition",
        )
        self.assertEqual(
            selected, ["9002/images/elite-1.jpg", "9002/images/elite-2.jpg"]
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
            product_name="Produto Inexistente",
            page_url="https://example.com/products/produto-inexistente",
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
            "metadata": {"alt": "imagem produto"},
            "url": "https://cdn/x/image.jpg",
        }
        self.assertTrue(_is_potential_table_candidate(candidate))


class TestUploadToApiErrorHandling(TestCase):
    """Tests for upload asset error reporting behavior."""

    def test_upload_reports_error_when_create_product_fails(self):
        """Asset must report queue error and re-raise upload exceptions."""
        page = ScrapedPage.objects.create(
            store_slug="demo-store", url="https://example.com/product"
        )
        item = ScrapedItem.objects.create(
            store_slug="demo-store",
            external_id="demo-1",
            name="Demo Product",
            source_page=page,
            status=ScrapedItem.Status.PROCESSING,
            price=99.9,
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
        )

        api = _FakeApiClient(create_raises=RuntimeError("create failed"))
        client = _FakeClientResource(api)
        context = build_asset_context()

        config = ItemConfig(item_id=item.id, url=page.url, store_slug="demo-store")
        metadata = RawScrapedData(
            name="Demo Product",
            brand_name="Demo Brand",
            description="Description",
            price=99.9,
            stock_status="A",
        )
        product_analysis = {
            "items": [{"name": "Demo Product", "packaging": "CONTAINER"}]
        }

        with self.assertRaises(RuntimeError):
            _ = upload_to_api(
                context=context,
                config=config,
                client=client,
                product_analysis=product_analysis,
                scraped_metadata=metadata,
            )

        self.assertEqual(len(api.report_error_calls), 1)
        reported_item_id, _message, is_fatal = api.report_error_calls[0]
        self.assertEqual(reported_item_id, item.id)
        self.assertFalse(is_fatal)


class _FakeScraperService:
    """Test double for scraper resource methods."""

    def __init__(self):
        self.extract_metadata_result: dict = {"opengraph": []}
        self.consolidate_result = RawScrapedData(name="N", brand_name="B")
        self.extract_raises: Exception | None = None
        self.download_assets_calls: list[tuple[int, str]] = []

    def download_assets(self, item_id: int, url: str):
        """Track download call and return storage path."""
        self.download_assets_calls.append((item_id, url))
        return f"{item_id}/source.html"

    def extract_metadata(self, _storage_path: str, _url: str):
        """Return metadata or raise configured exception."""
        if self.extract_raises:
            raise self.extract_raises
        return self.extract_metadata_result

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
        item = ScrapedItem.objects.create(
            store_slug="demo-store",
            external_id="item-1",
            name="Item",
            status=ScrapedItem.Status.NEW,
        )
        api = _FakeApiClient()
        scraper = _FakeScraperService()
        result = downloaded_assets(
            context=build_asset_context(),
            config=ItemConfig(
                item_id=item.id,
                url="https://example.com/p1",
                store_slug="demo-store",
            ),
            scraper=_FakeScraperResource(scraper),
            client=_FakeClientResource(api),
        )

        item.refresh_from_db()
        self.assertIsNotNone(item.source_page_id)
        self.assertEqual(result["origin_item_id"], item.id)
        self.assertEqual(result["storage_path"], f"{item.source_page_id}/source.html")

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

    @patch("agents.assets.run_raw_extraction", return_value="RAW-TEXT")
    def test_ocr_extraction_uses_candidates_manifest(self, mock_raw):
        """Selects image paths from candidates and forwards them to raw extraction."""
        candidates = (
            b'[{"file":"images/a.jpg","score":10,"nutrition_signal":3,"metadata":{"alt":"Tabela nutricional sabor chocolate"}},'
            b' {"file":"images/b.jpg","score":8,"nutrition_signal":0,"metadata":{"alt":"Produto sabor chocolate"}}]'
        )
        storage = _FakeStorage({"15/candidates.json": candidates})
        result = ocr_extraction(
            context=build_asset_context(),
            storage=_FakeStorageResource(storage),
            client=_FakeClientResource(_FakeApiClient()),
            scraped_metadata=RawScrapedData(
                name="Produto",
                brand_name="Marca",
                description="Desc",
            ),
            downloaded_assets={
                "origin_item_id": 1,
                "url": "https://x",
                "storage_path": "15/source.html",
            },
        )

        self.assertEqual(result, "RAW-TEXT")
        call_kwargs = mock_raw.call_args.kwargs
        self.assertEqual(call_kwargs["name"], "Produto")
        self.assertEqual(len(call_kwargs["image_paths"]), 2)
        self.assertEqual(call_kwargs["image_paths"][0], "15/images/a.jpg")
        self.assertIn("[IMAGE_SEQUENCE_CONTEXT]", call_kwargs["description"])
        self.assertIn("kind=NUTRITION_TABLE", call_kwargs["description"])
        self.assertIn("kind=PRODUCT_IMAGE", call_kwargs["description"])

    @patch("agents.assets.run_structured_extraction")
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

    @patch("agents.assets.run_structured_extraction")
    def test_product_analysis_retries_when_raw_has_more_variants(self, mock_structured):
        """Retries structured extraction when OCR indicates more variants than output."""
        mock_structured.side_effect = [
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Elitebar",
                        flavor_names=["Amendoim"],
                        variant_name="Amendoim",
                        is_variant=True,
                    )
                ]
            ),
            ProductAnalysisList(
                items=[
                    ProductAnalysisResult(
                        name="Elitebar",
                        flavor_names=["Amendoim"],
                        variant_name="Amendoim",
                        is_variant=True,
                    ),
                    ProductAnalysisResult(
                        name="Elitebar",
                        flavor_names=["Cookies & Cream"],
                        variant_name="Cookies & Cream",
                        is_variant=True,
                    ),
                ]
            ),
        ]
        api = _FakeApiClient()
        raw_text = "### 4. SABORES DISPONIVEIS\n- Amendoim\n- Cookies & Cream\n- Coco\n"

        result = product_analysis(
            context=build_asset_context(),
            config=ItemConfig(item_id=91, url="https://x", store_slug="demo"),
            client=_FakeClientResource(api),
            ocr_extraction=raw_text,
        )

        self.assertEqual(mock_structured.call_count, 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][1]["variant_name"], "Cookies & Cream")

    @patch("agents.assets.run_structured_extraction")
    def test_product_analysis_skips_retry_when_consistent(self, mock_structured):
        """Keeps single structured call when variant count is already consistent."""
        mock_structured.return_value = ProductAnalysisList(
            items=[
                ProductAnalysisResult(
                    name="Produto",
                    flavor_names=["Chocolate", "Baunilha"],
                    variant_name="Chocolate",
                    is_variant=True,
                ),
                ProductAnalysisResult(
                    name="Produto",
                    flavor_names=["Baunilha"],
                    variant_name="Baunilha",
                    is_variant=True,
                ),
            ]
        )
        api = _FakeApiClient()
        raw_text = "### 4. SABORES DISPONIVEIS\n- Chocolate\n- Baunilha\n"

        result = product_analysis(
            context=build_asset_context(),
            config=ItemConfig(item_id=92, url="https://x", store_slug="demo"),
            client=_FakeClientResource(api),
            ocr_extraction=raw_text,
        )

        self.assertEqual(mock_structured.call_count, 1)
        self.assertEqual(len(result["items"]), 2)

    def test_upload_to_api_creates_additional_variant_items(self):
        """Creates extra ScrapedItem entries when analysis returns multiple items."""
        page = ScrapedPage.objects.create(
            store_slug="demo-store",
            url="https://example.com/product",
        )
        origin = ScrapedItem.objects.create(
            store_slug="demo-store",
            external_id="demo-origin",
            name="Origin",
            source_page=page,
            status=ScrapedItem.Status.PROCESSING,
            price=90,
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
        )
        api = _FakeApiClient()

        result = upload_to_api(
            context=build_asset_context(),
            config=ItemConfig(item_id=origin.id, url=page.url, store_slug="demo-store"),
            client=_FakeClientResource(api),
            product_analysis={
                "items": [
                    {"name": "Produto Base", "packaging": "CONTAINER"},
                    {
                        "name": "Produto Base",
                        "variant_name": "Chocolate",
                        "packaging": "CONTAINER",
                    },
                ]
            },
            scraped_metadata=RawScrapedData(
                name="Produto Base",
                brand_name="Marca",
                description="Desc",
                price=90,
                stock_status="A",
            ),
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(len(api.create_calls), 2)
        self.assertTrue(
            ScrapedItem.objects.filter(
                store_slug="demo-store", external_id__contains="::v2-"
            ).exists()
        )

    def test_upload_to_api_skips_already_linked_item(self):
        """Skips create_product when scraped item is already linked."""
        brand = Brand.objects.create(name="brand", display_name="Brand")
        store = Store.objects.create(name="demo-store", display_name="Demo Store")
        product = Product.objects.create(name="Linked Product", brand=brand, weight=900)
        product_store = ProductStore.objects.create(
            product=product,
            store=store,
            external_id="demo-linked",
            product_link="https://example.com/already-linked",
        )

        page = ScrapedPage.objects.create(
            store_slug="demo-store",
            url="https://example.com/already-linked",
        )
        origin = ScrapedItem.objects.create(
            store_slug="demo-store",
            external_id="demo-linked",
            name="Linked",
            source_page=page,
            status=ScrapedItem.Status.LINKED,
            product_store=product_store,
            price=90,
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
        )
        api = _FakeApiClient()

        result = upload_to_api(
            context=build_asset_context(),
            config=ItemConfig(item_id=origin.id, url=page.url, store_slug="demo-store"),
            client=_FakeClientResource(api),
            product_analysis={"items": [{"name": "Linked", "packaging": "CONTAINER"}]},
            scraped_metadata=RawScrapedData(
                name="Linked",
                brand_name="Marca",
                description="Desc",
                price=90,
                stock_status="A",
            ),
        )

        self.assertEqual(len(api.create_calls), 0)
        self.assertTrue(result[0]["skipped"])
