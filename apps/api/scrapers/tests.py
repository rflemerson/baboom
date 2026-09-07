"""Tests for scraper spiders and ingestion helpers."""

import json
import logging
import os
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from unittest import skipUnless
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
from strawberry.django.views import GraphQLView

from baboom.schema import schema
from core.models import APIKey, Brand, Product, ProductStore, Store
from core.units import to_canonical
from offers.models import Offer, PriceObservation, StockStatus
from scrapers.admin import queue_for_agents
from scrapers.dtos import (
    AgentExtractionSubmitInput,
    ScrapedItemApprovalInput,
    ScrapedItemIngestionInput,
)
from scrapers.images import image_urls
from scrapers.models import ScrapedItem, ScrapedItemExtraction, ScrapedPage, ScraperRun
from scrapers.services import (
    RenderResult,
    ScrapedItemApprovalService,
    ScrapedItemCheckoutService,
    ScrapedItemErrorService,
    ScrapedItemExtractionSubmitService,
    ScrapedItemReviewStateService,
    ScraperService,
    extract_schema_metadata,
)
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
    release_stuck_items,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpResponse

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

    def test_checkout_can_target_one_queued_item(self) -> None:
        """Interactive review can reserve the item selected by the operator."""
        first = _scraped_item(
            store_slug="dark_lab",
            external_id="first-queued",
            status=ScrapedItem.Status.QUEUED,
            source_page=self.page,
        )
        selected = _scraped_item(
            store_slug="dark_lab",
            external_id="selected-queued",
            status=ScrapedItem.Status.QUEUED,
            source_page=self.page,
        )

        work = ScrapedItemCheckoutService().execute(item_id=selected.id)

        assert work is not None
        assert work.id == selected.id
        first.refresh_from_db()
        assert first.status == ScrapedItem.Status.QUEUED


class ScrapedItemReviewStateServiceTests(TestCase):
    """Tests for resumable local review state transitions."""

    def setUp(self) -> None:
        """Create one active interactive review."""
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/review",
        )
        self.item = _scraped_item(
            store_slug="growth",
            external_id="review-state",
            status=ScrapedItem.Status.PROCESSING,
            source_page=self.page,
        )
        self.service = ScrapedItemReviewStateService()

    def test_heartbeat_refreshes_last_attempt(self) -> None:
        """A local conversation can keep its checkout active."""
        previous_attempt = self.item.last_attempt_at

        item = self.service.heartbeat(item_id=self.item.id)

        assert item.status == ScrapedItem.Status.PROCESSING
        assert item.last_attempt_at is not None
        assert item.last_attempt_at != previous_attempt

    def test_release_returns_item_to_queue(self) -> None:
        """Abandoning a conversation should not manufacture an error."""
        item = self.service.release(item_id=self.item.id)

        assert item.status == ScrapedItem.Status.QUEUED
        assert item.last_attempt_at is None

    def test_heartbeat_and_release_reject_inactive_items(self) -> None:
        """Completed review must not be returned to processing by state actions."""
        self.item.status = ScrapedItem.Status.LINKED
        self.item.save(update_fields=["status"])
        for action, message in (
            (self.service.heartbeat, "not processing"),
            (self.service.release, "not processing"),
            (self.service.ignore, "cannot be ignored"),
        ):
            with (
                self.subTest(action=action.__name__),
                self.assertRaisesMessage(DjangoValidationError, message),
            ):
                action(item_id=self.item.id)
        self.item.refresh_from_db()
        assert self.item.status == ScrapedItem.Status.LINKED

    def test_timeout_requeues_expired_reservations_but_respects_heartbeat(self) -> None:
        """Only inactive reservations expire, without counting an extraction error."""
        old_attempt = timezone.now() - timedelta(hours=2)
        ScrapedItem.objects.filter(id=self.item.id).update(last_attempt_at=old_attempt)
        self.service.heartbeat(item_id=self.item.id)
        release_stuck_items()
        self.item.refresh_from_db()
        assert self.item.status == ScrapedItem.Status.PROCESSING
        ScrapedItem.objects.filter(id=self.item.id).update(last_attempt_at=old_attempt)
        release_stuck_items()
        self.item.refresh_from_db()
        assert self.item.status == ScrapedItem.Status.QUEUED
        assert self.item.last_attempt_at is None
        assert self.item.error_count == 0


class ScrapedItemApprovalServiceTests(TestCase):
    """Tests for explicit and idempotent catalog approval."""

    def setUp(self) -> None:
        """Create a reviewed extraction and matching catalog references."""
        self.brand = Brand.objects.create(
            name="growth",
            display_name="Growth",
        )
        self.store = Store.objects.create(
            name="growth",
            display_name="Growth",
        )
        self.page = ScrapedPage.objects.create(
            store_slug="growth",
            url="https://growth.example/approved",
        )
        self.item = _scraped_item(
            store_slug="growth",
            external_id="approved-item",
            name="Whey Test",
            status=ScrapedItem.Status.REVIEW,
            source_page=self.page,
        )
        ScrapedItemExtraction.objects.create(
            scraped_item=self.item,
            source_page=self.page,
            extracted_product={"name": "Whey Test", "brandName": "Growth"},
        )
        self.service = ScrapedItemApprovalService()

    def test_approval_can_link_an_existing_product_idempotently(self) -> None:
        """Repeating the approved request must not duplicate the store link."""
        product = Product.objects.create(name="Whey Test", brand=self.brand)
        data = ScrapedItemApprovalInput(itemId=self.item.id, productId=product.id)

        first_result = self.service.execute(data)
        second_result = self.service.execute(data)

        self.item.refresh_from_db()
        assert first_result == product
        assert second_result == product
        assert self.item.status == ScrapedItem.Status.LINKED
        links = ProductStore.objects.filter(product=product, offer=self.item.offer)
        assert links.count() == 1

    def test_approval_can_create_an_unpublished_product(self) -> None:
        """New products stay unpublished until a manager explicitly publishes them."""
        data = ScrapedItemApprovalInput.model_validate(
            {
                "itemId": self.item.id,
                "createProduct": {
                    "name": "Whey Test",
                    "brandId": self.brand.id,
                    "netMass": 1000,
                },
            },
        )

        product = self.service.execute(data)

        assert not product.is_published
        assert self.service.execute(data).pk == product.pk
        assert Product.objects.count() == 1
        assert product.net_mass == to_canonical(Decimal(1000), "g")
        links = ProductStore.objects.filter(product=product, offer=self.item.offer)
        assert links.exists()

    def test_approval_rejects_publication_and_invalid_metadata(self) -> None:
        """Rejected catalog input leaves both the review and catalog unchanged."""
        invalid_fields = (
            {"isPublished": True},
            {"name": ""},
            {"packaging": "INVALID"},
            {"categoryId": 999999},
            {"tagIds": [999999]},
        )
        for fields in invalid_fields:
            with self.subTest(fields=fields):
                data = ScrapedItemApprovalInput.model_validate(
                    {
                        "itemId": self.item.id,
                        "createProduct": {
                            "name": "Whey",
                            "brandId": self.brand.id,
                            **fields,
                        },
                    },
                )
                with self.assertRaisesMessage(
                    DjangoValidationError,
                    next(iter(fields)),
                ):
                    self.service.execute(data)
                assert not Product.objects.exists()
                assert not ProductStore.objects.exists()
                self.item.refresh_from_db()
                assert self.item.status == ScrapedItem.Status.REVIEW

    def test_approval_rolls_back_new_product_when_store_is_missing(self) -> None:
        """A failed offer link must not leave an orphan product."""
        self.store.delete()
        data = ScrapedItemApprovalInput.model_validate(
            {
                "itemId": self.item.id,
                "createProduct": {"name": "Whey", "brandId": self.brand.id},
            },
        )
        with self.assertRaisesMessage(DjangoValidationError, "not configured"):
            self.service.execute(data)
        assert not Product.objects.exists()

    def test_approval_requires_staging_and_one_target(self) -> None:
        """Approval cannot bypass staging or accept ambiguous targets."""
        product = Product.objects.create(name="Whey", brand=self.brand)
        for payload in (
            {"itemId": self.item.id},
            {
                "itemId": self.item.id,
                "productId": product.id,
                "createProduct": {"name": "Whey", "brandId": self.brand.id},
            },
        ):
            with (
                self.subTest(payload=payload),
                self.assertRaisesMessage(
                    DjangoValidationError,
                    "exactly one",
                ),
            ):
                self.service.execute(ScrapedItemApprovalInput.model_validate(payload))
        self.item.agent_extraction.delete()
        with self.assertRaisesMessage(DjangoValidationError, "no staged extraction"):
            self.service.execute(
                ScrapedItemApprovalInput(itemId=self.item.id, productId=product.id),
            )
        assert not ProductStore.objects.exists()

    def test_approved_item_cannot_be_retargeted(self) -> None:
        """A repeated approval for a different product must report a conflict."""
        first = Product.objects.create(name="First", brand=self.brand)
        other = Product.objects.create(name="Other", brand=self.brand)
        self.service.execute(
            ScrapedItemApprovalInput(itemId=self.item.id, productId=first.id),
        )
        with self.assertRaisesMessage(DjangoValidationError, "already approved"):
            self.service.execute(
                ScrapedItemApprovalInput(itemId=self.item.id, productId=other.id),
            )
        assert ProductStore.objects.get(offer=self.item.offer).product_id == first.id


class ReviewImageTests(SimpleTestCase):
    """Image normalization must preserve evidence without returning page links."""

    def test_image_references_are_normalized_and_deduplicated(self) -> None:
        """Support extensionless image fields, relative URLs and nested images."""
        payload = {
            "url": "https://shop.example/product",
            "@context": "https://schema.org",
            "images": [
                {"url": "/media/label", "alt": "Nutrition"},
                "//cdn.example/photo.jpg",
                "",
                "http://[malformed",
            ],
            "nested": {"imageUrl": "/media/label"},
            "properties": [["og:image", "/preview"]],
            "unsafe": {"image": "javascript:alert(1)"},
        }
        assert image_urls(payload, base_url="https://shop.example/product") == [
            "https://shop.example/media/label",
            "https://cdn.example/photo.jpg",
            "https://shop.example/preview",
        ]


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
        self.item.status = ScrapedItem.Status.LINKED
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

        with self.assertRaisesMessage(DjangoValidationError, "processing or in review"):
            ScrapedItemExtractionSubmitService().execute(data)

    def test_review_draft_can_be_revised_without_creating_catalog_data(self) -> None:
        """Resubmission replaces the staged tree and keeps the item in review."""
        service = ScrapedItemExtractionSubmitService()
        data = AgentExtractionSubmitInput.model_validate(
            {"originScrapedItemId": self.item.id, "product": {"name": "First"}},
        )
        first = service.execute(data)
        data.product.name = "Corrected"
        second = service.execute(data)
        self.item.refresh_from_db()
        assert first.pk == second.pk
        assert second.extracted_product["name"] == "Corrected"
        assert self.item.status == ScrapedItem.Status.REVIEW
        assert not Product.objects.exists()

    def test_submission_rejects_another_items_source_page(self) -> None:
        """A draft cannot silently change the source evidence to another page."""
        other = ScrapedPage.objects.create(url="https://growth.example/other")
        data = AgentExtractionSubmitInput.model_validate(
            {
                "originScrapedItemId": self.item.id,
                "sourcePageId": other.id,
                "product": {"name": "Wrong source"},
            },
        )
        with self.assertRaisesMessage(DjangoValidationError, "does not belong"):
            ScrapedItemExtractionSubmitService().execute(data)
        assert not ScrapedItemExtraction.objects.exists()


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

    def test_review_item_query_can_resume_without_changing_state(self) -> None:
        """A local client can reload the full item context by stable id."""
        query = """
        query ReviewItem($itemId: Int!) {
          reviewItem(itemId: $itemId) {
            id
            name
            status
            sourcePageId
            sourcePageContext
            sourcePageStructuredData
            imageUrls
          }
        }
        """
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": query, "variables": {"itemId": self.item.id}}),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key_obj.key,
        )

        response = cast("HttpResponse", self.view(request))
        payload = json.loads(response.content)

        self.item.refresh_from_db()
        assert "errors" not in payload
        assert int(payload["data"]["reviewItem"]["id"]) == self.item.id
        assert self.item.status == ScrapedItem.Status.PROCESSING

    def _graphql(self, query: str, *, authenticated: bool = True) -> dict:
        """Execute a GraphQL document through the HTTP authentication boundary."""
        request = self.factory.post(
            "/graphql/",
            data=json.dumps({"query": query}),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key_obj.key if authenticated else "",
        )
        response = cast("HttpResponse", self.view(request))
        return json.loads(response.content)

    def test_queue_defaults_to_queued_and_does_not_reserve(self) -> None:
        """Discovery excludes active items unless a status is explicitly requested."""
        queued = _scraped_item(
            store_slug="growth",
            external_id="queued-discovery",
            status=ScrapedItem.Status.QUEUED,
            source_page=self.page,
        )
        payload = self._graphql("{ reviewQueue { id status } }")
        assert "errors" not in payload
        assert [int(item["id"]) for item in payload["data"]["reviewQueue"]] == [
            queued.id,
        ]
        queued.refresh_from_db()
        assert queued.status == ScrapedItem.Status.QUEUED

    def test_catalog_discovery_includes_unpublished_products(self) -> None:
        """Duplicate search must include drafts as well as published catalog data."""
        brand = Brand.objects.create(name="growth", display_name="Growth")
        product = Product.objects.create(name="Whey", brand=brand)
        payload = self._graphql(
            '{ catalogCandidates(search: "Whey") { id isPublished } '
            'catalogBrands(search: "Growth") { id name } '
            "catalogCategories { id name } catalogTags { id name } }",
        )
        assert "errors" not in payload
        assert payload["data"]["catalogCandidates"] == [
            {"id": product.id, "isPublished": False},
        ]
        assert payload["data"]["catalogBrands"] == [{"id": brand.id, "name": "Growth"}]

    def test_review_discovery_requires_api_key(self) -> None:
        """The review queue must not expose merchant context to public clients."""
        payload = self._graphql("{ reviewQueue { id } }", authenticated=False)
        assert payload.get("errors")
        assert not payload.get("data")

    def test_approval_mutation_returns_validation_errors_then_links(self) -> None:
        """The remote approval boundary requires staging and returns catalog output."""
        brand = Brand.objects.create(name="growth", display_name="Growth")
        Store.objects.create(name="growth", display_name="Growth")
        product = Product.objects.create(name="Whey", brand=brand)
        query = (
            "mutation { approveScrapedItem(data: {"
            f"itemId: {self.item.id}, productId: {product.id}"
            "}) { product { id } errors { field message } } }"
        )
        rejected = self._graphql(query)
        assert rejected["data"]["approveScrapedItem"]["errors"]
        ScrapedItemExtractionSubmitService().execute(
            AgentExtractionSubmitInput.model_validate(
                {"originScrapedItemId": self.item.id, "product": {"name": "Whey"}},
            ),
        )
        accepted = self._graphql(query)
        assert "errors" not in accepted
        assert accepted["data"]["approveScrapedItem"] == {
            "product": {"id": product.id},
            "errors": None,
        }

    def test_release_scraped_item_mutation_returns_item_to_queue(self) -> None:
        """The GraphQL contract exposes a non-error abandonment path."""
        mutation = """
        mutation ReleaseItem($data: ScrapedItemActionInput!) {
          releaseScrapedItem(data: $data) {
            item { id status }
            errors { field message }
          }
        }
        """
        request = self.factory.post(
            "/graphql/",
            data=json.dumps(
                {
                    "query": mutation,
                    "variables": {"data": {"itemId": self.item.id}},
                },
            ),
            content_type="application/json",
            HTTP_X_API_KEY=self.api_key_obj.key,
        )

        response = cast("HttpResponse", self.view(request))
        payload = json.loads(response.content)

        self.item.refresh_from_db()
        assert payload["data"]["releaseScrapedItem"]["errors"] is None
        assert self.item.status == ScrapedItem.Status.QUEUED


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
    def _page() -> ScrapedPage:
        return ScrapedPage.objects.create(
            store_slug="dark_lab",
            url="https://example.com/product",
        )

    def test_enrich_page_renders_and_stores_raw_and_structured(self) -> None:
        """Every page is rendered; raw HTML, metadata and response info stored.

        Embedded ``<script>`` JSON survives because it lives in ``raw_html``.
        """
        page = self._page()
        rendered_html = (
            "<html><body>"
            '<script type="application/ld+json">'
            '{"@type": "Product", "name": "3W Whey Protein"}'
            "</script>"
            '<script>window.__NUXT__={"proteinas":"24g"}</script>'
            '<div class="nutri"><span>Proteínas</span><span>24 g</span></div>'
            "</body></html>"
        )
        result = RenderResult(200, {"etag": 'W/"abc"'}, rendered_html)
        with patch.object(
            ScraperService,
            "_render_page",
            return_value=result,
        ) as mock_render:
            stats = ScraperService.enrich_pages(limit=1)

        page.refresh_from_db()
        assert stats["updated"] == 1
        mock_render.assert_called_once()
        assert page.html_structured_data["json-ld"][0]["name"] == "3W Whey Protein"
        # raw HTML is the source of truth: it keeps the embedded script dataset.
        assert "window.__NUXT__" in page.raw_html
        assert page.response_meta == {"status": 200, "headers": {"etag": 'W/"abc"'}}

    def test_enrich_page_clears_captures_for_missing_page(self) -> None:
        """A 404/410 drops stale captures instead of keeping them."""
        page = self._page()
        page.raw_html = "<html>old</html>"
        page.html_structured_data = {"json-ld": [{"@type": "Product"}]}
        page.save(update_fields=["raw_html", "html_structured_data"])

        result = RenderResult(404, {}, "<html><body>not found</body></html>")
        with patch.object(ScraperService, "_render_page", return_value=result):
            stats = ScraperService.enrich_pages(limit=1)

        page.refresh_from_db()
        assert stats["updated"] == 1
        assert page.raw_html == ""
        assert page.html_structured_data == {}

    def test_enrich_page_failed_when_render_fails(self) -> None:
        """A failed render reports failure and leaves stored captures untouched."""
        page = self._page()
        page.raw_html = "<html>kept</html>"
        page.save(update_fields=["raw_html"])

        with patch.object(ScraperService, "_render_page", return_value=None):
            stats = ScraperService.enrich_pages(limit=1)

        page.refresh_from_db()
        assert stats["failed"] == 1
        # Prior capture is preserved rather than wiped on a transient failure.
        assert page.raw_html == "<html>kept</html>"

    def test_enrich_pages_rejects_non_positive_limit(self) -> None:
        """Invalid limits should fail before building a queryset slice."""
        with self.assertRaisesMessage(ValueError, "limit must be a positive integer"):
            ScraperService.enrich_pages(limit=0)


class SchemaMetadataParsingTests(SimpleTestCase):
    """Unit tests for schema.org metadata extraction."""

    def test_extracts_json_ld(self) -> None:
        """JSON-LD product metadata is parsed from the HTML."""
        html = """
        <html><body>
          <script type="application/ld+json">
          {"@type": "Product", "name": "Whey", "offers": {"price": "99.90"}}
          </script>
        </body></html>
        """
        data = extract_schema_metadata(html, "https://x.com/p")

        assert data["json-ld"][0]["name"] == "Whey"

    def test_page_without_metadata_returns_empty_syntaxes(self) -> None:
        """A page with no embedded metadata yields empty syntax lists."""
        data = extract_schema_metadata(
            "<html><body><p>oi</p></body></html>",
            "https://x.com/p",
        )

        assert all(not block for block in data.values())


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
