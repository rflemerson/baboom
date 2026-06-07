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
from core.models import APIKey
from offers.models import Offer, PriceObservation, StockStatus
from scrapers.admin import queue_for_agents
from scrapers.dtos import AgentExtractionSubmitInput, ScrapedItemIngestionInput
from scrapers.models import ScrapedItem, ScrapedItemExtraction, ScrapedPage, ScraperRun
from scrapers.services import (
    ScrapedItemCheckoutService,
    ScrapedItemErrorService,
    ScrapedItemExtractionSubmitService,
    ScraperService,
)
from scrapers.spiders.blackskull import BlackSkullSpider
from scrapers.spiders.catalog_api_spider import CatalogApiSpider
from scrapers.spiders.dark_lab import DarkLabSpider
from scrapers.spiders.dux import DuxSpider
from scrapers.spiders.growth import GrowthSpider
from scrapers.spiders.http_client import HttpClient
from scrapers.spiders.soldiers import SoldiersSpider
from scrapers.spiders.vtex_search_spider import VtexSearchSpider
from scrapers.tasks import _run_spider_monitor

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


def _fake_html_response(
    status: int = 200,
    *,
    etag: str = 'W/"x"',
    last_modified: str = "",
) -> MagicMock:
    """Build a fake HTML response for the conditional enrichment path."""
    response = MagicMock()
    response.status_code = status
    response.text = "<html></html>"
    response.headers = {"ETag": etag, "Last-Modified": last_modified}
    return response


def _scraped_item(
    **kwargs: object,
) -> ScrapedItem:
    """Create a pipeline scraped item backed by a merchant offer for tests."""
    store_slug = cast("str", kwargs["store_slug"])
    external_id = cast("str", kwargs["external_id"])
    name = cast("str", kwargs.get("name", ""))
    price = cast("Decimal | float | None", kwargs.get("price"))
    stock_status = cast("str", kwargs.get("stock_status", StockStatus.AVAILABLE))
    status = cast("str", kwargs.get("status", ScrapedItem.Status.NEW))
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
        status=status,
        source_page=source_page,
    )


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

        with self.assertRaisesRegex(RuntimeError, "blocked by upstream"):  # noqa: PT027
            _run_spider_monitor(FailingSpider, "Blocked Store")

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
        spider = DuxSpider(categories=["proteinas"])

        items = spider.crawl()

        assert len(items) > 0, "Dux spider should return items"
        assert ScrapedItem.objects.filter(offer__store_slug="dux_nutrition").count() > 0

        first = ScrapedItem.objects.filter(offer__store_slug="dux_nutrition").first()
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
        # The pipeline record is created and bound to the offer.
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


class ScrapedItemQueueTests(TestCase):
    """Tests for explicit agent queue selection."""

    def setUp(self) -> None:
        """Create one source page shared by queue items."""
        self.factory = RequestFactory()
        self.page = ScrapedPage.objects.create(
            store_slug="dark_lab",
            url="https://example.com/product",
        )

    def test_queue_for_agents_marks_selected_items(self) -> None:
        """Admin action should move selected items into the explicit queue."""
        item = _scraped_item(
            store_slug="dark_lab",
            external_id="568",
            status=ScrapedItem.Status.NEW,
            source_page=self.page,
        )
        request = self.factory.post("/admin/scrapers/scrapeditem/")
        modeladmin = MagicMock()

        queue_for_agents(modeladmin, request, ScrapedItem.objects.filter(id=item.id))

        item.refresh_from_db()
        assert item.status == ScrapedItem.Status.QUEUED
        modeladmin.message_user.assert_called_once()

    def test_checkout_only_consumes_queued_items(self) -> None:
        """Checkout should ignore NEW items until they are explicitly queued."""
        _scraped_item(
            store_slug="dark_lab",
            external_id="new-item",
            status=ScrapedItem.Status.NEW,
            source_page=self.page,
        )
        queued_item = _scraped_item(
            store_slug="dark_lab",
            external_id="queued-item",
            status=ScrapedItem.Status.QUEUED,
            source_page=self.page,
        )

        work = ScrapedItemCheckoutService().execute()

        assert work is not None
        assert work.id == queued_item.id
        queued_item.refresh_from_db()
        assert queued_item.status == ScrapedItem.Status.PROCESSING


class ScrapedItemErrorServiceTests(TestCase):
    """Unit tests for agent error reporting."""

    def setUp(self) -> None:
        """Create one processing item for error reporting tests."""
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        self.item = _scraped_item(
            store_slug="growth",
            external_id="growth-error-1",
            name="Whey Growth",
            status=ScrapedItem.Status.PROCESSING,
            source_page=self.page,
        )
        self.service = ScrapedItemErrorService()

    def test_execute_records_retryable_error(self) -> None:
        """Retryable errors move processing items to the retry state."""
        result = self.service.execute(
            item_id=self.item.id,
            message="temporary parse failure",
            is_fatal=False,
        )

        self.item.refresh_from_db()
        assert result
        assert self.item.status == ScrapedItem.Status.ERROR
        assert self.item.error_count == 1
        assert self.item.last_error_log == "temporary parse failure"

    def test_execute_records_fatal_error_for_review(self) -> None:
        """Fatal errors should move directly to review."""
        result = self.service.execute(
            item_id=self.item.id,
            message="unsupported page",
            is_fatal=True,
        )

        self.item.refresh_from_db()
        assert result
        assert self.item.status == ScrapedItem.Status.REVIEW
        assert self.item.error_count == 0
        assert self.item.last_error_log == "FATAL: unsupported page"

    def test_execute_rejects_non_processing_item(self) -> None:
        """Only currently checked out items can receive agent errors."""
        self.item.status = ScrapedItem.Status.REVIEW
        self.item.save(update_fields=["status"])

        result = self.service.execute(
            item_id=self.item.id,
            message="late error",
            is_fatal=False,
        )

        self.item.refresh_from_db()
        assert not result
        assert self.item.status == ScrapedItem.Status.REVIEW
        assert self.item.error_count == 0


class ScrapedItemExtractionSubmitServiceTests(TestCase):
    """Unit tests for staging agent extraction output."""

    def setUp(self) -> None:
        """Set up one scraped item with source context."""
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/whey",
        )
        self.item = _scraped_item(
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

    def test_execute_rejects_non_processing_item(self) -> None:
        """Agent submissions must belong to a checked out item."""
        self.item.status = ScrapedItem.Status.REVIEW
        self.item.save(update_fields=["status"])
        data = AgentExtractionSubmitInput.model_validate(
            {
                "originScrapedItemId": self.item.id,
                "sourcePageId": self.page.id,
                "sourcePageUrl": self.page.url,
                "storeSlug": "growth",
                "imageReport": "",
                "product": {
                    "name": "Whey Growth",
                    "brandName": "Growth",
                    "children": [],
                },
            },
        )

        with self.assertRaisesMessage(Exception, "Scraped item is not processing"):
            ScrapedItemExtractionSubmitService().execute(data)


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
        self.item = _scraped_item(
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

    def test_report_scraped_item_error_mutation_records_error(self) -> None:
        """The mutation lets agents report checkout processing failures."""
        mutation = """
        mutation ReportScrapedItemError($data: ScrapedItemErrorInput!) {
          reportScrapedItemError(data: $data)
        }
        """
        variables = {
            "data": {
                "itemId": self.item.id,
                "message": "temporary model failure",
                "isFatal": False,
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

        self.item.refresh_from_db()
        assert payload["data"]["reportScrapedItemError"]
        assert self.item.status == ScrapedItem.Status.ERROR
        assert self.item.error_count == 1
        assert self.item.last_error_log == "temporary model failure"


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


class ScraperEnrichmentTests(TestCase):
    """Unit tests for the on-demand HTML enrichment pass."""

    @staticmethod
    def _page(etag: str = "", last_modified: str = "") -> ScrapedPage:
        return ScrapedPage.objects.create(
            store_slug="dark_lab",
            url="https://example.com/product",
            http_etag=etag,
            http_last_modified=last_modified,
        )

    def test_enrich_page_skips_unchanged_304(self) -> None:
        """A 304 keeps stored data and writes nothing."""
        page = self._page(etag='W/"abc"')
        with patch.object(
            ScraperService,
            "_fetch_html_for_extraction",
            return_value=_fake_html_response(304),
        ):
            stats = ScraperService.enrich_pages(limit=1)

        page.refresh_from_db()
        assert stats["unchanged"] == 1
        assert page.http_etag == 'W/"abc"'

    def test_enrich_page_updates_on_200(self) -> None:
        """A 200 re-parses the HTML and records the fresh validators."""
        page = self._page()
        response = _fake_html_response(
            etag='W/"new"',
            last_modified="Wed, 21 Oct 2025 07:28:00 GMT",
        )
        with (
            patch.object(
                ScraperService,
                "_fetch_html_for_extraction",
                return_value=response,
            ),
            patch("scrapers.services.extruct.extract", return_value={"json-ld": []}),
        ):
            stats = ScraperService.enrich_pages(limit=1)

        page.refresh_from_db()
        assert stats["updated"] == 1
        assert page.html_structured_data == {"json-ld": []}
        assert page.http_etag == 'W/"new"'
        assert page.http_last_modified == "Wed, 21 Oct 2025 07:28:00 GMT"

    def test_enrich_page_failed_on_no_response(self) -> None:
        """A blocked/failed fetch reports failure without writing."""
        self._page()
        with patch.object(
            ScraperService,
            "_fetch_html_for_extraction",
            return_value=None,
        ):
            stats = ScraperService.enrich_pages(limit=1)

        assert stats["failed"] == 1

    def test_enrich_page_sends_conditional_validators(self) -> None:
        """Stored ETag/Last-Modified are sent as conditional request headers."""
        _ = self._page(etag='W/"abc"', last_modified="some-date")
        with patch.object(
            ScraperService,
            "_fetch_html_for_extraction",
            return_value=_fake_html_response(304),
        ) as mock_fetch:
            ScraperService.enrich_pages(limit=1)

        sent_headers = mock_fetch.call_args.args[1]
        assert sent_headers["If-None-Match"] == 'W/"abc"'
        assert sent_headers["If-Modified-Since"] == "some-date"

    def test_enrich_pages_rejects_non_positive_limit(self) -> None:
        """Invalid limits should fail before building a queryset slice."""
        with self.assertRaisesMessage(ValueError, "limit must be a positive integer"):
            ScraperService.enrich_pages(limit=0)


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
