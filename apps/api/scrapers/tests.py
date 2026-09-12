"""Tests for scraper spiders and ingestion helpers."""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING, cast
from unittest import skipUnless
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Brand, Product, ProductStore, Store
from offers.models import Offer, PriceObservation, StockStatus
from scrapers.dtos import ScrapedItemIngestionInput
from scrapers.models import ScrapedItem, ScrapedPage, ScraperRun
from scrapers.services import ScraperService
from scrapers.spiders.blackskull import BlackSkullSpider
from scrapers.spiders.catalog_api_spider import CatalogApiSpider
from scrapers.spiders.dark_lab import DarkLabSpider
from scrapers.spiders.dux import DuxSpider
from scrapers.spiders.growth import GrowthSpider
from scrapers.spiders.http_client import HttpClient
from scrapers.spiders.integral_medica import IntegralMedicaSpider
from scrapers.spiders.shopify_api_spider import ShopifyApiSpider
from scrapers.spiders.soldiers import SoldiersSpider
from scrapers.spiders.vtex_search_spider import VtexSearchSpider
from scrapers.tasks import (
    EmptyMonitorRunError,
    _run_spider_monitor,
)

if TYPE_CHECKING:
    from collections.abc import Callable

EXPECTED_EXTERNAL_STOCK_QUANTITY = 100
EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE = 2
EXPECTED_COMMA_DECIMAL_PRICE = 149.9
EXPECTED_SHOPIFY_JS_PRICE = 13.9
EXPECTED_GROWTH_DECIMAL_PRICE = 139.9
EXPECTED_GROWTH_CURRENCY_PRICE = 89.5
EXPECTED_VTEX_DECIMAL_PRICE = 99.9
EXPECTED_VTEX_INTEGER_PRICE = 55.0
DUX_EXPECTED_STOCK = 42
EXPECTED_MONITOR_ITEMS = 2


def _raised(operation: Callable[[], object], expected: type[Exception]) -> Exception:
    """Return the exception an operation is expected to raise."""
    try:
        operation()
    except expected as error:
        return error
    message = f"Expected {expected.__name__} to be raised."
    raise AssertionError(message)


EXPECTED_FALLBACK_CATEGORY_COUNT = 2
EXPECTED_SCRAPER_RUN_ITEMS = 2

type ScrapedJsonObject = dict[str, object]

# Disable logging during tests
logging.getLogger("scrapers").setLevel(logging.CRITICAL)


class HttpClientTests(SimpleTestCase):
    """Unit tests for the shared HTTP client."""

    def test_get_treats_success_status_waf_block_as_failure(self) -> None:
        """A 200 block page should not be returned as a usable response."""
        response = MagicMock()
        response.status_code = 200
        response.text = "Cloudflare Access Denied"
        session = MagicMock()
        session.get.return_value = response

        with patch("scrapers.spiders.http_client.cffi_requests.Session") as session_cls:
            session_cls.return_value = session
            result = HttpClient().get("https://example.com/protected")

        assert result is None


def _scraped_item(
    **kwargs: object,
) -> ScrapedItem:
    """Create a scraped item backed by a merchant offer for tests."""
    store_slug = cast("str", kwargs["store_slug"])
    external_id = cast("str", kwargs["external_id"])
    name = cast("str", kwargs.get("name", ""))
    price = cast("Decimal | float | None", kwargs.get("price"))
    stock_status = cast("str", kwargs.get("stock_status", StockStatus.AVAILABLE))
    source_page = cast("ScrapedPage | None", kwargs.get("source_page"))
    resolved_price = Decimal(str(price)) if price is not None else None
    offer = Offer.objects.create(
        store_slug=store_slug,
        external_id=external_id,
        name=name,
        url=source_page.url if source_page else "",
        current_price=resolved_price,
        current_stock_status=stock_status,
    )
    return ScrapedItem.objects.create(
        offer=offer,
        source_page=source_page,
    )


class ScrapedItemAdminWorkflowTests(TestCase):
    """The human admin flow carries a captured offer into the catalog."""

    def test_create_product_prefills_and_links_existing_offer(self) -> None:
        """Creating a product reuses the offer, price, and store identity."""
        user = get_user_model().objects.create(
            username="catalog-admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(user)
        Brand.objects.create(name="growth", display_name="Growth")
        store = Store.objects.create(name="growth", display_name="Growth")
        item = _scraped_item(
            store_slug="growth",
            external_id="whey-450",
            name="Whey 450 g",
            price=Decimal("79.90"),
        )
        item.offer.url = "https://example.com/whey-450"
        item.offer.save(update_fields=["url"])
        PriceObservation.objects.create(
            offer=item.offer,
            price=Decimal("79.90"),
            stock_status=StockStatus.AVAILABLE,
        )

        action = self.client.post(
            reverse("admin:scrapers_scrapeditem_changelist"),
            {
                "action": "create_product_from_scraped_item",
                "_selected_action": [item.pk],
            },
        )
        assert action.status_code == HTTPStatus.FOUND
        add_url = action["Location"]
        assert f"source_offer={item.offer_id}" in add_url

        add_form = self.client.get(add_url)
        assert add_form.status_code == HTTPStatus.OK
        assert add_form.context["adminform"].form.initial["name"] == "Whey 450 g"
        listing = next(
            inline.formset
            for inline in add_form.context["inline_admin_formsets"]
            if inline.opts.model is ProductStore
        )
        assert listing.forms[0].initial["store"] == store.pk
        assert listing.forms[0].initial["price"] == Decimal("79.90")

        post_data = {
            "name": "Whey 450 g",
            "kind": Product.Kind.SIMPLE,
            "brand": Brand.objects.get(name="growth").pk,
            "net_mass": "450",
            "ean": "",
            "description": "",
            "packaging": Product.Packaging.CONTAINER,
            "category": "",
            "_save": "Save",
        }
        for inline in add_form.context["inline_admin_formsets"]:
            prefix = inline.formset.prefix
            post_data[f"{prefix}-TOTAL_FORMS"] = str(inline.formset.total_form_count())
            post_data[f"{prefix}-INITIAL_FORMS"] = "0"
            post_data[f"{prefix}-MIN_NUM_FORMS"] = "0"
            post_data[f"{prefix}-MAX_NUM_FORMS"] = "1000"
            if inline.opts.model is ProductStore:
                post_data.update(
                    {
                        f"{prefix}-0-store": str(store.pk),
                        f"{prefix}-0-external_id": item.offer.external_id,
                        f"{prefix}-0-product_link": item.offer.url,
                        f"{prefix}-0-price": "79.90",
                        f"{prefix}-0-stock_status": StockStatus.AVAILABLE,
                    },
                )

        saved = self.client.post(add_url, post_data)
        assert saved.status_code == HTTPStatus.FOUND
        product = Product.objects.get(name="Whey 450 g")
        assert ProductStore.objects.get(product=product).offer_id == item.offer_id
        assert PriceObservation.objects.filter(offer=item.offer).count() == 1


class ScrapedItemIngestionInputTests(SimpleTestCase):
    """Unit tests for scraper ingestion DTO normalization."""

    def test_normalizes_invalid_ean_suffix_to_blank(self) -> None:
        """VTEX bundle labels with GTIN-looking prefixes should not hit the DB."""
        input_data = ScrapedItemIngestionInput(
            store_slug="black_skull",
            external_id="445",
            ean="7898708737105KIT",
        )

        assert input_data.ean == ""

    def test_normalizes_descriptive_ean_to_blank(self) -> None:
        """Descriptive bundle labels are not valid EAN/GTIN identifiers."""
        input_data = ScrapedItemIngestionInput(
            store_slug="max_titanium",
            external_id="333",
            ean="Whey Pro Morango +Horus Limao",
        )

        assert input_data.ean == ""

    def test_keeps_valid_gtin_14(self) -> None:
        """Valid GTIN values should still be persisted."""
        input_data = ScrapedItemIngestionInput(
            store_slug="black_skull",
            external_id="445",
            ean="7898708737105",
        )

        assert input_data.ean == "7898708737105"


class ScraperRunHistoryTests(TestCase):
    """Tests for scraper monitor execution history."""

    def test_monitor_success_creates_scraper_run(self) -> None:
        """Successful monitor runs should be visible in admin history."""

        class SuccessfulSpider:
            def crawl(self) -> list[object]:
                return [object(), object()]

        result = _run_spider_monitor(SuccessfulSpider, "Test Store")
        run = ScraperRun.objects.get()

        assert result == "Test Store Monitor: Saved/Updated 2 items."
        assert run.label == "Test Store"
        assert run.status == ScraperRun.Status.SUCCESS
        assert run.items_count == EXPECTED_SCRAPER_RUN_ITEMS
        assert run.finished_at is not None
        assert run.duration_ms is not None
        assert run.error_message == ""

    def test_monitor_error_creates_failed_scraper_run(self) -> None:
        """Failed monitor runs should record the error before re-raising."""

        class FailingSpider:
            def crawl(self) -> list[object]:
                msg = "blocked by upstream"
                raise RuntimeError(msg)

        error = _raised(
            lambda: _run_spider_monitor(FailingSpider, "Blocked Store"),
            RuntimeError,
        )

        assert str(error) == "blocked by upstream"

        run = ScraperRun.objects.get()
        assert run.label == "Blocked Store"
        assert run.status == ScraperRun.Status.ERROR
        assert run.items_count == 0
        assert run.finished_at is not None
        assert run.duration_ms is not None
        assert run.message == "Blocked Store Monitor failed."
        assert run.error_message == "blocked by upstream"


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
        assert ScrapedItem.objects.filter(offer__store_slug="black_skull").count() > 0

        first = ScrapedItem.objects.filter(offer__store_slug="black_skull").first()
        assert first is not None

    def test_darklab_spider(self) -> None:
        """Test DarkLab spider execution."""
        spider = DarkLabSpider(categories=["whey-protein"])

        items = spider.crawl()

        assert len(items) > 0, "DarkLab spider should return items"
        assert ScrapedItem.objects.filter(offer__store_slug="dark_lab").count() > 0

        first = ScrapedItem.objects.filter(offer__store_slug="dark_lab").first()
        assert first is not None

    def test_dux_spider(self) -> None:
        """Test Dux spider execution."""
        spider = DuxSpider(categories=["produtos"])

        items = spider.crawl()

        assert len(items) > 0, "Dux spider should return items"
        assert ScrapedItem.objects.filter(offer__store_slug="dux_nutrition").count() > 0

        first = ScrapedItem.objects.filter(offer__store_slug="dux_nutrition").first()
        assert first is not None

    def test_integral_medica_spider(self) -> None:
        """Test Integralmedica spider execution."""
        spider = IntegralMedicaSpider(categories=["colecao-proteinas"])

        items = spider.crawl()

        assert len(items) > 0, "Integralmedica spider should return items"
        assert (
            ScrapedItem.objects.filter(offer__store_slug="integral_medica").count() > 0
        )

        first = ScrapedItem.objects.filter(offer__store_slug="integral_medica").first()
        assert first is not None

    def test_growth_spider(self) -> None:
        """Test Growth spider execution."""
        spider = GrowthSpider(categories=["/vegano/"])

        items = spider.crawl()

        assert len(items) > 0, "Growth spider should return items"
        assert ScrapedItem.objects.filter(offer__store_slug="growth").count() > 0

        first = ScrapedItem.objects.filter(offer__store_slug="growth").first()
        assert first is not None


class OfferObservationTests(TestCase):
    """Tests for recording offers and price observations from scraped data."""

    def _ingest(self, **overrides: object) -> ScrapedItemIngestionInput:
        """Build a scraped-item ingestion payload with sensible defaults."""
        defaults: dict[str, object] = {
            "store_slug": "test_store",
            "external_id": "TEST123",
            "name": "Test Whey 900g",
            "price": Decimal("199.90"),
            "stock_status": "A",
        }
        defaults.update(overrides)
        return ScrapedItemIngestionInput(**defaults)

    def test_save_product_records_offer_and_observation_without_link(self) -> None:
        """An offer and its first price are recorded even with no catalog link."""
        ScraperService.save_product(self._ingest())

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert offer.current_price == Decimal("199.90")
        assert offer.name == "Test Whey 900g"
        assert offer.price_observations.count() == 1
        # The source item is created and bound to the offer.
        assert ScrapedItem.objects.filter(offer=offer).count() == 1

    def test_repeated_same_price_does_not_duplicate_observation(self) -> None:
        """Re-seeing the same price keeps a single observation."""
        ScraperService.save_product(self._ingest())
        ScraperService.save_product(self._ingest())

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert offer.price_observations.count() == 1

    def test_repeated_same_price_updates_changed_api_context(self) -> None:
        """Catalog context should stay fresh even when price/stock are unchanged."""
        payload = self._ingest(url="https://example.com/test-product")
        ScraperService.save_product(payload, api_context={"version": 1})
        ScraperService.save_product(payload, api_context={"version": 2})

        page = ScrapedPage.objects.get(url="https://example.com/test-product")
        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert page.api_context == {"version": 2}
        assert offer.price_observations.count() == 1

    def test_price_change_appends_new_observation(self) -> None:
        """A changed price appends a second observation to the series."""
        ScraperService.save_product(self._ingest())
        ScraperService.save_product(self._ingest(price=Decimal("179.90")))

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert (
            offer.price_observations.count()
            == EXPECTED_PRICE_HISTORY_RECORDS_AFTER_UPDATE
        )
        assert offer.current_price == Decimal("179.90")
        latest = PriceObservation.objects.filter(offer=offer).latest("observed_at")
        assert latest.price == Decimal("179.90")

    def test_missing_price_records_offer_without_observation(self) -> None:
        """An offer with no price is still tracked, but logs no observation."""
        ScraperService.save_product(self._ingest(price=None))

        offer = Offer.objects.get(store_slug="test_store", external_id="TEST123")
        assert offer.current_price is None
        assert offer.price_observations.count() == 0


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
    def test_process_and_save_passes_api_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Light path hands the catalog context to save_product as api_context."""
        fake_obj = MagicMock()
        mock_save.return_value = fake_obj

        result = self.spider.process_item(self.base_item, "whey-protein")

        assert result == fake_obj
        context = json.loads(mock_save.call_args.kwargs["api_context"])
        assert context["platform"] == "shopify"
        assert "variants" in context
        assert "options" in context

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
        assert payload.stock_status == StockStatus.AVAILABLE


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

    @patch("scrapers.spiders.catalog_api_spider.HttpClient.get")
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
        assert payload.stock_status == StockStatus.AVAILABLE

    @patch("scrapers.spiders.shopify_api_spider.ScraperService.save_product")
    def test_process_and_save_passes_api_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Light path hands the catalog context to save_product as api_context."""
        fake_obj = MagicMock()
        mock_save.return_value = fake_obj

        result = self.spider.process_item(self.base_item, "barra")

        assert result == fake_obj
        context = json.loads(mock_save.call_args.kwargs["api_context"])
        assert context["platform"] == "shopify"
        assert "variants" in context
        assert "options" in context

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
        assert payload.stock_status == StockStatus.AVAILABLE

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
    def test_process_and_save_passes_api_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Light path hands the catalog context to save_product as api_context."""
        fake_obj = MagicMock()
        mock_save.return_value = fake_obj

        result = self.spider.process_item(self.base_item, "/proteina/")

        assert result == fake_obj
        context = json.loads(mock_save.call_args.kwargs["api_context"])
        assert context["platform"] == "uappi_wapstore"
        assert "prices" in context["product"]


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
        assert payload.stock_status == StockStatus.AVAILABLE

    def test_parse_price_supports_common_formats(self) -> None:
        """Parses decimal strings and rejects invalid price."""
        assert self.spider.parse_price("99,90") == EXPECTED_VTEX_DECIMAL_PRICE
        assert self.spider.parse_price(55) == EXPECTED_VTEX_INTEGER_PRICE
        assert self.spider.parse_price("N/A") is None

    @patch("scrapers.spiders.vtex_search_spider.ScraperService.save_product")
    def test_process_and_save_passes_api_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Light path hands the catalog context to save_product as api_context."""
        fake_obj = MagicMock()
        mock_save.return_value = fake_obj

        result = self.spider.process_item(self.base_item, "proteina")

        assert result == fake_obj
        context = json.loads(mock_save.call_args.kwargs["api_context"])
        assert context["platform"] == "vtex_legacy"
        assert "items" in context


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
        assert payload.stock_status == StockStatus.AVAILABLE

    @patch("scrapers.spiders.vtex_search_spider.ScraperService.save_product")
    def test_process_and_save_passes_api_context(
        self,
        mock_save: MagicMock,
    ) -> None:
        """Light path hands the catalog context to save_product as api_context."""
        fake_obj = MagicMock()
        mock_save.return_value = fake_obj

        result = self.spider.process_item(self.base_item, "proteina")

        assert result == fake_obj
        context = json.loads(mock_save.call_args.kwargs["api_context"])
        assert context["platform"] == "vtex_legacy"
        assert "items" in context


class DuxNuvemshopSpiderUnitTests(SimpleTestCase):
    """Unit tests for the Nuvemshop JSON-LD ingestion used by Dux."""

    LISTING_HTML = """
    <html><head>
      <script type="application/ld+json">
      {"@type": "Organization", "name": "Dux"}
      </script>
      <script type="application/ld+json">
      {"@type": "Product", "name": "Whey Protein Concentrado - Pote 900g",
       "sku": "410713009", "gtin13": "7898604470045",
       "offers": {"@type": "Offer",
         "url": "https://duxhumanhealth.com/produtos/whey-concentrado-900g/",
         "priceCurrency": "BRL", "price": "159.90",
         "availability": "http://schema.org/InStock",
         "inventoryLevel": {"@type": "QuantitativeValue", "value": "42"}}}
      </script>
      <script type="application/ld+json">not json at all</script>
    </head></html>
    """

    def setUp(self) -> None:
        """Create the spider and a reusable JSON-LD product entry."""
        self.spider = DuxSpider()
        self.base_item: ScrapedJsonObject = {
            "@type": "Product",
            "name": "Whey Protein Concentrado - Pote 900g",
            "sku": "410713009",
            "gtin13": "7898604470045",
            "offers": {
                "@type": "Offer",
                "url": "https://duxhumanhealth.com/produtos/whey-900g/",
                "price": "159.90",
                "availability": "http://schema.org/InStock",
                "inventoryLevel": {"value": "42"},
            },
        }

    def test_extract_products_keeps_only_product_blocks(self) -> None:
        """Organization blocks and malformed JSON must not become products."""
        products = self.spider.extract_products(self.LISTING_HTML)

        assert len(products) == 1
        assert products[0]["sku"] == "410713009"

    @patch("scrapers.spiders.nuvemshop_spider.ScraperService.save_product")
    def test_process_and_save_maps_offer_fields(self, mock_save: MagicMock) -> None:
        """Price, stock and identifiers come from the embedded offer."""
        fake_obj = MagicMock()
        mock_save.return_value = fake_obj

        result = self.spider.process_item(self.base_item, "produtos")

        assert result == fake_obj
        payload = mock_save.call_args.args[0]
        assert payload.external_id == "410713009"
        assert payload.ean == "7898604470045"
        assert payload.stock_quantity == DUX_EXPECTED_STOCK
        assert payload.stock_status == StockStatus.AVAILABLE
        assert payload.url == "https://duxhumanhealth.com/produtos/whey-900g/"

    @patch("scrapers.spiders.nuvemshop_spider.ScraperService.save_product")
    def test_out_of_stock_offer_zeroes_quantity(self, mock_save: MagicMock) -> None:
        """An unavailable offer is stored as out of stock with no units."""
        item = dict(self.base_item)
        item["offers"] = dict(
            cast("ScrapedJsonObject", self.base_item["offers"]),
            availability="http://schema.org/OutOfStock",
        )

        self.spider.process_item(item, "produtos")

        payload = mock_save.call_args.args[0]
        assert payload.stock_status == StockStatus.OUT_OF_STOCK
        assert payload.stock_quantity == 0

    @patch("scrapers.spiders.nuvemshop_spider.ScraperService.save_product")
    def test_process_and_save_skips_item_without_sku(
        self,
        mock_save: MagicMock,
    ) -> None:
        """The SKU is the external identifier, so an entry without one is skipped."""
        item = dict(self.base_item)
        item["sku"] = ""

        result = self.spider.process_item(item, "produtos")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.nuvemshop_spider.ScraperService.save_product")
    def test_process_and_save_skips_invalid_price(self, mock_save: MagicMock) -> None:
        """An offer without a usable price is not persisted."""
        item = dict(self.base_item)
        item["offers"] = dict(
            cast("ScrapedJsonObject", self.base_item["offers"]),
            price="sob consulta",
        )

        result = self.spider.process_item(item, "produtos")

        assert result is None
        mock_save.assert_not_called()

    @patch("scrapers.spiders.nuvemshop_spider.ScraperService.save_product")
    def test_process_and_save_passes_api_context(self, mock_save: MagicMock) -> None:
        """The full JSON-LD entry is handed downstream as the api context."""
        self.spider.process_item(self.base_item, "produtos")

        context = json.loads(mock_save.call_args.kwargs["api_context"])
        assert context["platform"] == "nuvemshop"
        assert context["product"]["sku"] == "410713009"


class IntegralMedicaSpiderUnitTests(SimpleTestCase):
    """Integralmedica now ingests through the Shopify template."""

    def test_spider_uses_the_shopify_template(self) -> None:
        """The VTEX endpoints are gone, so the spider must be Shopify-based."""
        spider = IntegralMedicaSpider()

        assert isinstance(spider, ShopifyApiSpider)
        assert spider.STORE_SLUG == "integral_medica"
        assert spider.BASE_URL.endswith(".myshopify.com")


class HttpClientBlockDetectionTests(SimpleTestCase):
    """The WAF detector must separate a challenge page from ordinary content."""

    def setUp(self) -> None:
        """Create a client to exercise the detector."""
        self.client = HttpClient()

    def test_cloudflare_analytics_is_not_a_block(self) -> None:
        """A catalog page shipping Cloudflare scripts is legitimate content."""
        page = (
            "<html><body><script>/* Cloudflare cache status of the request. */"
            "console.error('[web-vitals] could not read the Cloudflare cache status');"
            "</script><h1>Whey Protein</h1></body></html>"
        )

        assert self.client.is_blocked(page) is False

    def test_cloudflare_challenge_is_a_block(self) -> None:
        """The interstitial challenge page must still be detected."""
        page = "<html><title>Attention Required! | Cloudflare</title></html>"

        assert self.client.is_blocked(page) is True

    def test_sucuri_firewall_is_a_block(self) -> None:
        """Sucuri denial pages remain detected."""
        page = "<html><body>Sucuri WebSite Firewall - Access Denied</body></html>"

        assert self.client.is_blocked(page) is True


class EmptyMonitorRunTests(TestCase):
    """An empty run is an error only for a monitor that used to produce items."""

    LABEL = "Dux"

    def _run(self, items: list[object]) -> str:
        """Run the monitor helper with a spider returning the given items."""
        spider_class = MagicMock()
        spider_class.return_value.crawl.return_value = items
        return _run_spider_monitor(spider_class, self.LABEL)

    def test_empty_run_is_success_for_a_monitor_without_history(self) -> None:
        """A store that never produced items may legitimately return none."""
        message = self._run([])

        run = ScraperRun.objects.get()
        assert run.status == ScraperRun.Status.SUCCESS
        assert run.items_count == 0
        assert "0 items" in message

    def test_empty_run_fails_after_the_monitor_has_produced_items(self) -> None:
        """Going silently to zero is what hid the Dux and Integral breakages."""
        ScraperRun.objects.create(
            label=self.LABEL,
            status=ScraperRun.Status.SUCCESS,
            items_count=112,
        )

        _raised(lambda: self._run([]), EmptyMonitorRunError)

        run = ScraperRun.objects.filter(items_count=0).get()
        assert run.status == ScraperRun.Status.ERROR
        assert "most likely changed" in run.error_message

    def test_empty_run_of_another_monitor_does_not_raise(self) -> None:
        """History is per monitor, so a healthy store does not fail its peer."""
        ScraperRun.objects.create(
            label="Growth",
            status=ScraperRun.Status.SUCCESS,
            items_count=199,
        )

        self._run([])

        run = ScraperRun.objects.get(label=self.LABEL)
        assert run.status == ScraperRun.Status.SUCCESS

    def test_run_with_items_records_success(self) -> None:
        """The normal path still records the item count."""
        self._run([object(), object()])

        run = ScraperRun.objects.get()
        assert run.status == ScraperRun.Status.SUCCESS
        assert run.items_count == EXPECTED_MONITOR_ITEMS
