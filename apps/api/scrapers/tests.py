"""Tests for scraper spiders and ingestion helpers."""

import json
import logging
import os
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from unittest import skipUnless
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from strawberry.django.views import GraphQLView

from baboom.schema import schema
from core.models import APIKey, Brand, Product, ProductPriceHistory, ProductStore, Store
from scrapers.approval import ScrapedItemExtractionApproveService
from scrapers.dtos import AgentExtractionSubmitInput, ScrapedItemIngestionInput
from scrapers.models import ScrapedItem, ScrapedItemExtraction, ScrapedPage
from scrapers.services import ScrapedItemExtractionSubmitService, ScraperService
from scrapers.spiders.blackskull import BlackSkullSpider
from scrapers.spiders.catalog_api_spider import CatalogApiSpider
from scrapers.spiders.dark_lab import DarkLabSpider
from scrapers.spiders.dux import DuxSpider
from scrapers.spiders.growth import GrowthSpider
from scrapers.spiders.soldiers import SoldiersSpider
from scrapers.spiders.vtex_search_spider import VtexSearchSpider

if TYPE_CHECKING:
    from django.http import HttpResponse

EXPECTED_EXTERNAL_STOCK_QUANTITY = 100
EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE = 2
EXPECTED_COMMA_DECIMAL_PRICE = 149.9
EXPECTED_SHOPIFY_JS_PRICE = 13.9
EXPECTED_GROWTH_DECIMAL_PRICE = 139.9
EXPECTED_GROWTH_CURRENCY_PRICE = 89.5
EXPECTED_VTEX_DECIMAL_PRICE = 99.9
EXPECTED_VTEX_INTEGER_PRICE = 55.0
EXPECTED_FALLBACK_CATEGORY_COUNT = 2
EXPECTED_APPROVED_WHEY_WEIGHT = 900
EXPECTED_COMBO_COMPONENT_COUNT = 2

type ScrapedJsonObject = dict[str, object]

# Disable logging during tests
logging.getLogger("scrapers").setLevel(logging.CRITICAL)


@skipUnless(
    os.getenv("RUN_EXTERNAL_SCRAPER_TESTS") == "1",
    "External scraper integration tests are opt-in. Set RUN_EXTERNAL_SCRAPER_TESTS=1.",
)
class ScraperIntegrationTests(TestCase):
    """Integration tests for Spiders.

    Tests hitting REAL APIs.
    """

    def test_blackskull_spider(self) -> None:
        """Test BlackSkull spider execution."""
        spider = BlackSkullSpider(categories=["proteina"])

        items = spider.crawl()

        assert len(items) > 0, "BlackSkull spider should return items"
        assert ScrapedItem.objects.filter(store_slug="black_skull").count() > 0

        first = ScrapedItem.objects.filter(store_slug="black_skull").first()
        assert first is not None

    def test_darklab_spider(self) -> None:
        """Test DarkLab spider execution."""
        spider = DarkLabSpider(categories=["whey-protein"])

        items = spider.crawl()

        assert len(items) > 0, "DarkLab spider should return items"
        assert ScrapedItem.objects.filter(store_slug="dark_lab").count() > 0

        first = ScrapedItem.objects.filter(store_slug="dark_lab").first()
        assert first is not None

    def test_dux_spider(self) -> None:
        """Test Dux spider execution."""
        spider = DuxSpider(categories=["proteinas"])

        items = spider.crawl()

        assert len(items) > 0, "Dux spider should return items"
        assert ScrapedItem.objects.filter(store_slug="dux_nutrition").count() > 0

        first = ScrapedItem.objects.filter(store_slug="dux_nutrition").first()
        assert first is not None

    def test_growth_spider(self) -> None:
        """Test Growth spider execution."""
        spider = GrowthSpider(categories=["/vegano/"])

        items = spider.crawl()

        assert len(items) > 0, "Growth spider should return items"
        assert ScrapedItem.objects.filter(store_slug="growth").count() > 0

        first = ScrapedItem.objects.filter(store_slug="growth").first()
        assert first is not None


class SyncPriceToCoreTests(TestCase):
    """Unit tests for ScraperService logic (save_product and sync_price_to_core)."""

    def setUp(self) -> None:
        """Set up test data."""
        self.brand = Brand.objects.create(name="test_brand", display_name="Test Brand")
        self.store = Store.objects.create(name="test_store", display_name="Test Store")
        self.product = Product.objects.create(
            name="Test Whey",
            brand=self.brand,
            weight=900,
        )
        self.product_store = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="TEST123",
            product_link="https://test.com/product",
        )

    def test_save_product_creates_price_history_for_linked_item(self) -> None:
        """Test that saving a product creates a price history record."""
        ScrapedItem.objects.create(
            store_slug="test_store",
            external_id="TEST123",
            status=ScrapedItem.Status.LINKED,
            product_store=self.product_store,
            price=Decimal("100.00"),
        )

        input_data = ScrapedItemIngestionInput(
            store_slug="test_store",
            external_id="TEST123",
            price=Decimal("199.90"),
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
        )
        ScraperService.save_product(input_data)

        assert ProductPriceHistory.objects.count() == 1
        price_record = ProductPriceHistory.objects.first()

        # Ensure not None for MyPy
        if price_record is None:
            self.fail("Price history record should be created but was None")
        assert price_record.price == Decimal("199.90")

    def test_sync_logic_skips_if_price_unchanged(self) -> None:
        """Test that sync skips if price is unchanged."""
        ProductPriceHistory.objects.create(
            store_product_link=self.product_store,
            price=Decimal("199.90"),
            stock_status="A",
        )

        item = ScrapedItem.objects.create(
            store_slug="test_store",
            external_id="TEST123",
            price=Decimal("199.90"),
            stock_status="A",
            status=ScrapedItem.Status.LINKED,
            product_store=self.product_store,
        )

        result = ScraperService.sync_price_to_core(item)

        assert not result
        assert ProductPriceHistory.objects.count() == 1

    def test_sync_logic_creates_new_record_on_price_change(self) -> None:
        """Test that sync creates a new record on price change."""
        item = ScrapedItem.objects.create(
            store_slug="test_store",
            external_id="TEST123",
            price=Decimal("199.90"),
            stock_status="A",
            status=ScrapedItem.Status.LINKED,
            product_store=self.product_store,
        )

        ScraperService.sync_price_to_core(item)
        assert ProductPriceHistory.objects.count() == 1

        item.price = Decimal("179.90")
        item.save()

        ScraperService.sync_price_to_core(item)

        assert (
            ProductPriceHistory.objects.count()
            == EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE
        )

        try:
            latest = ProductPriceHistory.objects.latest("collected_at")
        except ProductPriceHistory.DoesNotExist:
            self.fail("Latest history not found")

        assert latest.price == Decimal("179.90")


class ScrapedItemExtractionSubmitServiceTests(TestCase):
    """Unit tests for staging agent extraction output."""

    def setUp(self) -> None:
        """Set up one scraped item with source context."""
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        self.item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-1",
            name="Whey Growth",
            status=ScrapedItem.Status.PROCESSING,
            source_page=self.page,
        )

    def test_execute_stages_extraction_and_moves_item_to_review(self) -> None:
        """Persist validated agent output without creating catalog records."""
        data = AgentExtractionSubmitInput.model_validate(
            {
                "originScrapedItemId": self.item.id,
                "sourcePageId": self.page.id,
                "sourcePageUrl": self.page.url,
                "storeSlug": "growth",
                "imageReport": "Image 1: whey label",
                "product": {
                    "name": "Whey Growth",
                    "brandName": "Growth",
                    "weightGrams": 900,
                    "children": [
                        {
                            "name": "Creatine",
                            "brandName": "Growth",
                            "weightGrams": 250,
                            "children": [],
                        },
                    ],
                },
            },
        )

        extraction = ScrapedItemExtractionSubmitService().execute(data)

        self.item.refresh_from_db()
        assert extraction.scraped_item == self.item
        assert extraction.source_page == self.page
        assert extraction.extracted_product["name"] == "Whey Growth"
        assert extraction.extracted_product["children"][0]["name"] == "Creatine"
        assert self.item.status == ScrapedItem.Status.REVIEW
        assert self.item.error_count == 0
        assert self.item.last_error_log == ""


class ScrapedItemExtractionGraphQLTests(TestCase):
    """GraphQL tests for agent extraction staging."""

    def setUp(self) -> None:
        """Set up authenticated GraphQL test client state."""
        self.factory = RequestFactory()
        self.api_key_obj = APIKey.objects.create(name="Agent Client")
        self.view = GraphQLView.as_view(schema=schema)
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        self.item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-graphql-1",
            name="Whey Growth",
            status=ScrapedItem.Status.PROCESSING,
            source_page=self.page,
        )

    def test_submit_agent_extraction_mutation_stages_payload(self) -> None:
        """The mutation stores the agent product tree for review."""
        mutation = """
        mutation SubmitAgentExtraction($data: AgentExtractionInput!) {
          submitAgentExtraction(data: $data) {
            extraction {
              id
              scrapedItemId
              sourcePageId
              extractedProduct
            }
            errors {
              field
              message
            }
          }
        }
        """
        variables = {
            "data": {
                "originScrapedItemId": self.item.id,
                "sourcePageId": self.page.id,
                "sourcePageUrl": self.page.url,
                "storeSlug": "growth",
                "imageReport": "Image 1: label",
                "product": {
                    "name": "Whey Growth",
                    "brandName": "Growth",
                    "children": [],
                },
            },
        }
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": mutation, "variables": variables}),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key_obj.key,
        )

        response = cast("HttpResponse", self.view(request))
        payload = json.loads(response.content)

        result = payload["data"]["submitAgentExtraction"]
        self.item.refresh_from_db()
        extraction = ScrapedItemExtraction.objects.get(scraped_item=self.item)
        assert result["errors"] is None
        assert result["extraction"]["scrapedItemId"] == self.item.id
        assert result["extraction"]["sourcePageId"] == self.page.id
        assert result["extraction"]["extractedProduct"]["name"] == "Whey Growth"
        assert extraction.image_report == "Image 1: label"
        assert self.item.status == ScrapedItem.Status.REVIEW


class ScrapedItemExtractionApproveServiceTests(TestCase):
    """Unit tests for approving staged agent extractions."""

    def setUp(self) -> None:
        """Set up one staged extraction with enough source data to approve."""
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        self.item = ScrapedItem.objects.create(
            store_slug="growth",
            external_id="growth-approve-1",
            name="Whey Growth",
            price=Decimal("149.90"),
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
            status=ScrapedItem.Status.REVIEW,
            source_page=self.page,
        )

    def test_execute_creates_product_and_links_origin_item(self) -> None:
        """Approval creates a catalog product from staged extraction JSON."""
        extraction = ScrapedItemExtraction.objects.create(
            scraped_item=self.item,
            source_page=self.page,
            image_report="Image 1: whey label",
            extracted_product={
                "name": "Whey Growth",
                "brandName": "Growth",
                "weightGrams": 900,
                "packaging": "REFILL",
                "categoryHierarchy": ["Proteins", "Whey"],
                "tagsHierarchy": [["Goal", "Hypertrophy"]],
                "flavorNames": ["Chocolate"],
                "nutritionFacts": {
                    "servingSizeGrams": 30,
                    "energyKcal": 120,
                    "proteins": 24,
                    "carbohydrates": 3,
                    "totalFats": 2,
                },
                "children": [],
            },
        )

        result = ScrapedItemExtractionApproveService().execute(
            extraction_id=extraction.id,
        )

        self.item.refresh_from_db()
        extraction.refresh_from_db()
        product = result.product
        assert product.name == "Whey Growth"
        assert product.weight == EXPECTED_APPROVED_WHEY_WEIGHT
        assert product.brand.display_name == "Growth"
        assert product.packaging == Product.Packaging.REFILL
        assert product.type == Product.Type.SIMPLE
        assert product.store_links.count() == 1
        assert product.nutrition_profiles.count() == 1
        assert self.item.status == ScrapedItem.Status.LINKED
        assert self.item.product_store_id is not None
        assert extraction.approved_product == product
        assert extraction.approved_at is not None

    def test_execute_creates_combo_with_children_components(self) -> None:
        """Approval maps extracted children into combo components."""
        extraction = ScrapedItemExtraction.objects.create(
            scraped_item=self.item,
            source_page=self.page,
            image_report="Image 1: combo",
            extracted_product={
                "name": "Combo Whey + Creatina",
                "brandName": "Growth",
                "weightGrams": 1200,
                "packaging": "OTHER",
                "children": [
                    {
                        "name": "Whey Growth",
                        "brandName": "Growth",
                        "weightGrams": 900,
                        "packaging": "REFILL",
                        "children": [],
                    },
                    {
                        "name": "Creatina Growth",
                        "brandName": "Growth",
                        "weightGrams": 300,
                        "packaging": "CONTAINER",
                        "quantity": 2,
                        "children": [],
                    },
                ],
            },
        )

        result = ScrapedItemExtractionApproveService().execute(
            extraction_id=extraction.id,
        )

        self.item.refresh_from_db()
        product = result.product
        assert product.type == Product.Type.COMBO
        assert product.component_links.count() == EXPECTED_COMBO_COMPONENT_COUNT
        assert set(
            product.component_links.values_list("component__name", flat=True),
        ) == {"Whey Growth", "Creatina Growth"}
        assert self.item.status == ScrapedItem.Status.LINKED

    def test_execute_rejects_extraction_missing_required_catalog_fields(self) -> None:
        """Approval fails clearly when the extracted product is incomplete."""
        extraction = ScrapedItemExtraction.objects.create(
            scraped_item=self.item,
            source_page=self.page,
            image_report="Image 1: incomplete",
            extracted_product={
                "name": "Whey Growth",
                "brandName": "Growth",
                "children": [],
            },
        )

        with self.assertRaisesMessage(Exception, "Product weight is required"):
            ScrapedItemExtractionApproveService().execute(extraction_id=extraction.id)

        self.item.refresh_from_db()
        assert Product.objects.count() == 0
        assert self.item.status == ScrapedItem.Status.REVIEW


class _DummyCatalogSpider(CatalogApiSpider):
    """Test double for category resolution behavior."""

    BRAND_NAME = "Dummy"
    FALLBACK_CATEGORIES = ("fallback-a", "fallback-b")

    def __init__(
        self,
        categories: list[str] | None = None,
        dynamic_categories: list[str] | None = None,
    ) -> None:
        super().__init__(categories)
        self.dynamic_categories = dynamic_categories or []

    def _fetch_categories(self) -> list[str]:
        return list(self.dynamic_categories)

    def _crawl_category(
        self,
        category: str,
        processed_ids: set[str],
    ) -> list[object]:
        _ = category, processed_ids
        return []


class CatalogApiSpiderTests(SimpleTestCase):
    """Unit tests for category source precedence."""

    def test_explicit_categories_override_dynamic_discovery(self) -> None:
        """Manual categories should constrain the crawl when provided."""
        spider = _DummyCatalogSpider(
            categories=["manual-only"],
            dynamic_categories=["dynamic-a", "dynamic-b"],
        )

        categories = spider.crawl()

        assert categories == []
        assert spider.metrics["categories_discovered"] == 1
        assert spider.metrics["categories_crawled"] == 1

    def test_fallback_categories_used_when_dynamic_is_empty(self) -> None:
        """Fallback categories should still work when discovery returns nothing."""
        spider = _DummyCatalogSpider(dynamic_categories=[])

        categories = spider.crawl()

        assert categories == []
        assert (
            spider.metrics["categories_discovered"] == EXPECTED_FALLBACK_CATEGORY_COUNT
        )
        assert spider.metrics["categories_crawled"] == EXPECTED_FALLBACK_CATEGORY_COUNT


class ScraperServiceContextPersistenceTests(SimpleTestCase):
    """Unit tests for Django-side context persistence helper."""

    def test_persist_page_context_updates_source_page_json_fields(
        self,
    ) -> None:
        """Writes API and HTML-structured payloads into source page."""
        fake_page = MagicMock()
        fake_page.url = "https://example.com/product"
        fake_item = MagicMock()
        fake_item.source_page_id = 123
        fake_item.source_page = fake_page

        with patch.object(
            ScraperService,
            "extract_html_structured_data",
            return_value={"json-ld": []},
        ):
            ScraperService.persist_page_context(fake_item, '{"platform":"shopify"}')

        assert fake_page.api_context == {"platform": "shopify"}
        assert fake_page.html_structured_data == {"json-ld": []}
        fake_page.save.assert_called_once_with(
            update_fields=["api_context", "html_structured_data"],
        )


class DarkLabSpiderUnitTests(SimpleTestCase):
    """Unit tests for DarkLab Shopify parsing behavior."""

    def setUp(self) -> None:
        """Create reusable Shopify fixture item."""
        self.spider = DarkLabSpider()
        self.base_item: ScrapedJsonObject = {
            "id": 123,
            "title": "Whey Test",
            "handle": "whey-test",
            "vendor": "Dark Lab",
            "product_type": "Whey",
            "tags": ["whey", "protein"],
            "options": [{"name": "Flavor", "values": ["Chocolate", "Vanilla"]}],
            "images": [{"src": "https://cdn.example.com/1.jpg"}],
            "variants": [
                {
                    "id": 111,
                    "title": "Chocolate",
                    "option1": "Chocolate",
                    "sku": "WHEY-CHOCO",
                    "barcode": "1234567890123",
                    "price": "129.90",
                    "available": True,
                    "inventory_quantity": 7,
                },
            ],
        }

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_skips_item_without_handle(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Should skip item when Shopify handle is missing."""
        item = dict(self.base_item)
        item["handle"] = ""

        result = self.spider.process_item(item, "whey-protein")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_skips_invalid_price(self, mock_save: MagicMock) -> None:
        """Should skip item when selected variant has invalid price."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], price="N/A")]

        result = self.spider.process_item(item, "whey-protein")

        assert result is None
        mock_save.assert_not_called()

    def test_parse_price_handles_comma_decimal(self) -> None:
        """Parses prices with comma decimal separator."""
        value = self.spider.parse_price("149,90")
        assert value == EXPECTED_COMMA_DECIMAL_PRICE

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_persists_shopify_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Writes structured Shopify context into source_page api_context."""
        fake_source_page = MagicMock()
        fake_source_page.url = "https://example.com/product"
        fake_obj = MagicMock()
        fake_obj.source_page_id = 10
        fake_obj.source_page = fake_source_page
        mock_save.return_value = fake_obj

        with patch.object(
            ScraperService,
            "extract_html_structured_data",
            return_value={"json-ld": []},
        ):
            result = self.spider.process_item(self.base_item, "whey-protein")

        assert result == fake_obj
        assert fake_source_page.api_context["platform"] == "shopify"
        assert "variants" in fake_source_page.api_context
        assert "options" in fake_source_page.api_context
        fake_source_page.save.assert_called_once_with(
            update_fields=["api_context", "html_structured_data"],
        )

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_keeps_available_on_unknown_shopify_stock(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Available Shopify items without quantity should keep stock unknown."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], inventory_quantity=None)]

        _ = self.spider.process_item(item, "whey-protein")

        payload = mock_save.call_args.args[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == ScrapedItem.StockStatus.AVAILABLE


class SoldiersSpiderUnitTests(SimpleTestCase):
    """Unit tests for Soldiers Shopify API spider behavior."""

    def setUp(self) -> None:
        """Create reusable Shopify fixture item."""
        self.spider = SoldiersSpider()
        self.base_item: ScrapedJsonObject = {
            "id": 456,
            "title": "Elitebar 30g Protein Bar - Soldiers Nutrition",
            "handle": "elitebar-30g-barra-de-proteina-soldiers-nutrition",
            "vendor": "Soldiers Nutrition",
            "type": "barra",
            "tags": ["barra", "proteina"],
            "options": [
                {"name": "Quantity", "values": ["3 Units", "6 Units"]},
                {"name": "Flavor", "values": ["Peanut", "Cookies"]},
            ],
            "images": ["https://cdn.example.com/a.webp"],
            "variants": [
                {
                    "id": 999,
                    "title": "3 Units / Peanut",
                    "price": "13,90",
                    "available": True,
                    "inventory_quantity": None,
                    "barcode": "",
                    "sku": "3UA",
                },
            ],
        }

    @patch("scrapers.spiders.catalog_api_spider.requests.get")
    def test_fetch_categories_from_collections_api(self, mock_get: MagicMock) -> None:
        """Loads category handles from collections endpoint."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "collections": [{"handle": "whey"}, {"handle": "creatina"}],
        }
        mock_get.return_value = response

        categories = self.spider.fetch_categories()

        assert "whey" in categories
        assert "creatina" in categories

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_skips_without_handle(self, mock_save: MagicMock) -> None:
        """Skips item when handle is missing."""
        item = dict(self.base_item)
        item["handle"] = ""

        result = self.spider.process_item(item, "barra")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_skips_invalid_price(self, mock_save: MagicMock) -> None:
        """Skips item when selected variant has invalid price."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], price="N/A")]

        result = self.spider.process_item(item, "barra")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_keeps_available_on_unknown_shopify_stock(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Available Shopify items without quantity should keep stock unknown."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], inventory_quantity=None)]

        _ = self.spider.process_item(item, "barra")

        payload = mock_save.call_args.args[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == ScrapedItem.StockStatus.AVAILABLE

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_persists_shopify_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Writes structured Shopify context into source_page api_context."""
        fake_source_page = MagicMock()
        fake_source_page.url = "https://example.com/product"
        fake_obj = MagicMock()
        fake_obj.source_page_id = 20
        fake_obj.source_page = fake_source_page
        mock_save.return_value = fake_obj

        with patch.object(
            ScraperService,
            "extract_html_structured_data",
            return_value={"json-ld": []},
        ):
            result = self.spider.process_item(self.base_item, "barra")

        assert result == fake_obj
        assert fake_source_page.api_context["platform"] == "shopify"
        assert "variants" in fake_source_page.api_context
        assert "options" in fake_source_page.api_context
        fake_source_page.save.assert_called_once_with(
            update_fields=["api_context", "html_structured_data"],
        )

    def test_parse_price_handles_shopify_js_cents(self) -> None:
        """Converts integer cents from product.js into decimal reais."""
        assert self.spider.parse_price(1390) == EXPECTED_SHOPIFY_JS_PRICE
        assert self.spider.parse_price("1390") == EXPECTED_SHOPIFY_JS_PRICE


class GrowthSpiderUnitTests(SimpleTestCase):
    """Unit tests for Growth API parsing behavior."""

    def setUp(self) -> None:
        """Create reusable Growth fixture item."""
        self.spider = GrowthSpider()
        self.base_item: ScrapedJsonObject = {
            "id": 1001,
            "nome": "Whey Growth",
            "sku": "WHEY1001",
            "link": "/whey-growth",
            "precos": {"por": "139,90"},
            "estoque": 42,
            "ean": "7890000000011",
        }

    @patch("scrapers.spiders.wapstore_api_spider.ScraperService.save_product")
    def test_process_and_save_skips_without_valid_url(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Skips items when URL is missing/invalid."""
        item = dict(self.base_item)
        item["link"] = ""

        result = self.spider.process_item(item, "/proteina/")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.wapstore_api_spider.ScraperService.save_product")
    def test_process_and_save_skips_invalid_price(self, mock_save: MagicMock) -> None:
        """Skips item when price is not parseable."""
        item = dict(self.base_item)
        item["precos"] = {"por": "N/A"}

        result = self.spider.process_item(item, "/proteina/")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.wapstore_api_spider.ScraperService.save_product")
    def test_process_and_save_keeps_available_on_unknown_stock(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Unknown stock should not be forced to out-of-stock."""
        item = dict(self.base_item)
        item["estoque"] = "unknown"

        _ = self.spider.process_item(item, "/proteina/")

        payload = mock_save.call_args.args[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == ScrapedItem.StockStatus.AVAILABLE

    def test_parse_price_supports_currency_formats(self) -> None:
        """Parses price tokens from common API payload formats."""
        assert self.spider.parse_price("139,90") == EXPECTED_GROWTH_DECIMAL_PRICE
        assert self.spider.parse_price("R$ 89.50") == EXPECTED_GROWTH_CURRENCY_PRICE
        assert self.spider.parse_price("N/A") is None

    def test_category_path_filter_rejects_non_product_routes(self) -> None:
        """Rejects account/checkout-like paths from dynamic menu."""
        assert not self.spider.is_valid_category_path("/conta/meus-pedidos/")
        assert not self.spider.is_valid_category_path("/checkout/")
        assert self.spider.is_valid_category_path("/proteina/")

    @patch("scrapers.spiders.wapstore_api_spider.ScraperService.save_product")
    def test_process_and_save_persists_structured_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Writes structured Growth context into source_page api_context."""
        fake_source_page = MagicMock()
        fake_source_page.url = "https://example.com/product"
        fake_obj = MagicMock()
        fake_obj.source_page_id = 30
        fake_obj.source_page = fake_source_page
        mock_save.return_value = fake_obj

        with patch.object(
            ScraperService,
            "extract_html_structured_data",
            return_value={"json-ld": []},
        ):
            result = self.spider.process_item(self.base_item, "/proteina/")

        assert result == fake_obj
        assert fake_source_page.api_context["platform"] == "uappi_wapstore"
        assert "prices" in fake_source_page.api_context["product"]
        fake_source_page.save.assert_called_once_with(
            update_fields=["api_context", "html_structured_data"],
        )


class _DummyVtexSpider(VtexSearchSpider):
    """Concrete test double for VtexSearchSpider helper methods."""

    BRAND_NAME = "Dummy VTEX"
    STORE_SLUG = "dummy_vtex"
    BASE_URL = "https://dummy.example.com"


class VtexSpiderUnitTests(SimpleTestCase):
    """Unit tests for VTEX base spider parsing behavior."""

    def setUp(self) -> None:
        """Create reusable VTEX fixture item."""
        self.spider = _DummyVtexSpider()
        self.base_item: ScrapedJsonObject = {
            "productId": "9001",
            "productName": "VTEX Product",
            "linkText": "vtex-product",
            "items": [
                {
                    "itemId": "SKU-1",
                    "ean": "7890000000099",
                    "sellers": [
                        {
                            "sellerDefault": True,
                            "commertialOffer": {
                                "Price": "99,90",
                                "AvailableQuantity": 7,
                            },
                        },
                    ],
                },
            ],
        }

    @patch("scrapers.spiders.vtex_search_spider.ScraperService.save_product")
    def test_process_and_save_skips_without_valid_url(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Skips item when linkText is missing."""
        item = dict(self.base_item)
        item["linkText"] = ""

        result = self.spider.process_item(item, "proteina")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.vtex_search_spider.ScraperService.save_product")
    def test_process_and_save_skips_invalid_price(self, mock_save: MagicMock) -> None:
        """Skips item when price is not parseable."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["Price"] = "N/A"

        result = self.spider.process_item(item, "proteina")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.vtex_search_spider.ScraperService.save_product")
    def test_process_and_save_keeps_available_on_unknown_stock(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Unknown stock should keep item available by default."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = "x"

        _ = self.spider.process_item(item, "proteina")

        payload = mock_save.call_args.args[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == ScrapedItem.StockStatus.AVAILABLE

    def test_parse_price_supports_common_formats(self) -> None:
        """Parses decimal strings and rejects invalid price."""
        assert self.spider.parse_price("99,90") == EXPECTED_VTEX_DECIMAL_PRICE
        assert self.spider.parse_price(55) == EXPECTED_VTEX_INTEGER_PRICE
        assert self.spider.parse_price("N/A") is None

    @patch("scrapers.spiders.vtex_search_spider.ScraperService.save_product")
    def test_process_and_save_persists_structured_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Writes structured VTEX context into source_page api_context."""
        fake_source_page = MagicMock()
        fake_source_page.url = "https://example.com/product"
        fake_obj = MagicMock()
        fake_obj.source_page_id = 40
        fake_obj.source_page = fake_source_page
        mock_save.return_value = fake_obj

        with patch.object(
            ScraperService,
            "extract_html_structured_data",
            return_value={"json-ld": []},
        ):
            result = self.spider.process_item(self.base_item, "proteina")

        assert result == fake_obj
        assert fake_source_page.api_context["platform"] == "vtex_legacy"
        assert "items" in fake_source_page.api_context
        fake_source_page.save.assert_called_once_with(
            update_fields=["api_context", "html_structured_data"],
        )


class BlackSkullSpiderUnitTests(SimpleTestCase):
    """Unit tests for BlackSkull VTEX GraphQL parsing behavior."""

    def setUp(self) -> None:
        """Create reusable BlackSkull fixture item."""
        self.spider = BlackSkullSpider()
        self.base_item: ScrapedJsonObject = {
            "productId": "5001",
            "productName": "Whey Black Skull",
            "linkText": "whey-black-skull",
            "items": [
                {
                    "itemId": "BS-SKU-1",
                    "ean": "7890000000500",
                    "sellers": [
                        {
                            "sellerDefault": True,
                            "commertialOffer": {
                                "Price": "119,90",
                                "AvailableQuantity": 5,
                            },
                        },
                    ],
                },
            ],
        }

    @patch("scrapers.spiders.vtex_graphql_spider.ScraperService.save_product")
    def test_process_and_save_skips_without_valid_url(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Skips item when linkText is missing."""
        item = dict(self.base_item)
        item["linkText"] = ""

        result = self.spider.process_item(item, "proteina")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.vtex_graphql_spider.ScraperService.save_product")
    def test_process_and_save_skips_invalid_price(self, mock_save: MagicMock) -> None:
        """Skips item when price is not parseable."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["Price"] = "N/A"

        result = self.spider.process_item(item, "proteina")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.vtex_graphql_spider.ScraperService.save_product")
    def test_process_and_save_keeps_available_on_unknown_stock(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Unknown stock should keep item available by default."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = "x"

        _ = self.spider.process_item(item, "proteina")

        payload = mock_save.call_args.args[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == ScrapedItem.StockStatus.AVAILABLE

    @patch("scrapers.spiders.vtex_graphql_spider.ScraperService.save_product")
    def test_process_and_save_persists_structured_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Writes structured VTEX GraphQL context into source_page api_context."""
        fake_source_page = MagicMock()
        fake_source_page.url = "https://example.com/product"
        fake_obj = MagicMock()
        fake_obj.source_page_id = 50
        fake_obj.source_page = fake_source_page
        mock_save.return_value = fake_obj

        with patch.object(
            ScraperService,
            "extract_html_structured_data",
            return_value={"json-ld": []},
        ):
            result = self.spider.process_item(self.base_item, "proteina")

        assert result == fake_obj
        assert fake_source_page.api_context["platform"] == "vtex_graphql"
        assert "items" in fake_source_page.api_context
        fake_source_page.save.assert_called_once_with(
            update_fields=["api_context", "html_structured_data"],
        )
