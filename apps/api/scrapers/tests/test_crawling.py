"""Tests for the Scrapy crawling infrastructure."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest import skipUnless
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import SimpleTestCase, TestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.crawler.base import CatalogSpider
from scrapers.crawler.middlewares import (
    ImpersonationMiddleware,
    is_blocked,
    parse_retry_after,
)
from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.models import ScrapedItem
from scrapers.stores.blackskull import BlackSkullSpider
from scrapers.stores.dark_lab import DarkLabSpider
from scrapers.stores.dux import DuxSpider
from scrapers.stores.growth import GrowthSpider
from scrapers.stores.integral_medica import IntegralMedicaSpider
from scrapers.tests import EXPECTED_FALLBACK_CATEGORY_COUNT


@skipUnless(
    os.getenv("RUN_EXTERNAL_SCRAPER_TESTS") == "1",
    "External scraper integration tests are opt-in. Set RUN_EXTERNAL_SCRAPER_TESTS=1.",
)
class ScraperIntegrationTests(TestCase):
    """Opt-in tests that execute real Scrapy subprocesses."""

    def _run(self, spider_name: str) -> None:
        """Run one real spider through the same command used by Celery."""
        from pathlib import Path

        result = subprocess.run(
            [sys.executable, "-m", "scrapy", "crawl", spider_name],
            cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "DJANGO_SECRET_KEY": "dev-only"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    def test_blackskull_spider(self) -> None:
        """Test Black Skull spider execution."""
        self._run("blackskull")
        assert ScrapedItem.objects.filter(offer__store_slug="black_skull").exists()

    def test_darklab_spider(self) -> None:
        """Test Dark Lab spider execution."""
        self._run("dark_lab")
        assert ScrapedItem.objects.filter(offer__store_slug="dark_lab").exists()

    def test_dux_spider(self) -> None:
        """Test Dux spider execution."""
        self._run("dux")
        assert ScrapedItem.objects.filter(offer__store_slug="dux_nutrition").exists()

    def test_integral_medica_spider(self) -> None:
        """Test Integralmedica spider execution."""
        self._run("integral_medica")
        assert ScrapedItem.objects.filter(offer__store_slug="integral_medica").exists()

    def test_growth_spider(self) -> None:
        """Test Growth spider execution."""
        self._run("growth")
        assert ScrapedItem.objects.filter(offer__store_slug="growth").exists()


class _DummyCatalogSpider(CatalogSpider):
    """Small concrete spider for shared scheduling behavior."""

    name = "dummy-catalog"
    STORE_SLUG = "dummy"
    BASE_URL = "https://dummy.example.com"
    FALLBACK_CATEGORIES = ("fallback-a", "fallback-b")
    normalizer = DarkLabSpider.normalizer

    def category_discovery_request(self) -> Request:
        """Return a harmless discovery request for tests."""
        return Request(f"{self.BASE_URL}/categories")

    def category_request(self, category: str) -> Request:
        """Return one harmless category request for tests."""
        return Request(f"{self.BASE_URL}/{category}")


class CatalogSpiderTests(SimpleTestCase):
    """Tests for shared category, jitter, and deduplication behavior."""

    def test_explicit_categories_override_dynamic_discovery(self) -> None:
        """Manual categories constrain the initial requests."""
        spider = _DummyCatalogSpider(categories=["manual-only"])
        requests = list(spider.start_category_requests())
        assert [request.url for request in requests] == [
            "https://dummy.example.com/manual-only",
        ]

    def test_fallback_categories_used_when_dynamic_is_empty(self) -> None:
        """Fallback categories are scheduled when discovery returns none."""
        spider = _DummyCatalogSpider()
        requests = list(spider.requests_for_categories([]))
        assert len(requests) == EXPECTED_FALLBACK_CATEGORY_COUNT
        assert [request.url.rsplit("/", maxsplit=1)[-1] for request in requests] == [
            "fallback-a",
            "fallback-b",
        ]


class WafDetectionTests(SimpleTestCase):
    """The WAF detector separates challenge pages from ordinary content."""

    def test_cloudflare_analytics_is_not_a_block(self) -> None:
        """A page mentioning Cloudflare analytics remains valid content."""
        page = "<html><script>Cloudflare cache status</script><h1>Whey</h1></html>"
        assert is_blocked(page) is False

    def test_cloudflare_challenge_is_a_block(self) -> None:
        """The Cloudflare interstitial remains detected."""
        assert is_blocked("Attention Required! | Cloudflare") is True

    def test_sucuri_firewall_is_a_block(self) -> None:
        """Sucuri denial pages remain detected."""
        assert is_blocked("Sucuri WebSite Firewall - Access Denied") is True


class ProcessRawProductIntegrationTests(TestCase):
    """Concrete spiders pass configuration through normalization and pipeline."""

    def _persist(self, spider: CatalogSpider, raw: dict, category: str) -> list[object]:
        """Send normalized products through the production pipeline."""
        products = spider.process_raw_product(raw, category)
        pipeline = CatalogPipeline()
        for product in products:
            pipeline.process_item(product, spider)
        return products

    def test_shopify_passes_store_page_and_category_and_rejects_bad_payload(self) -> None:
        """Shopify wiring persists its configured store and source page."""
        spider = DarkLabSpider()
        assert self._persist(spider, {"id": "bad", "handle": "", "variants": []}, "whey") == []
        assert ScrapedItem.objects.count() == 0
        raw = {
            "id": "shopify-product-1",
            "title": "Whey Test",
            "handle": "whey-test",
            "variants": [{"id": "shopify-variant-1", "title": "Default Title", "price": "10.00", "available": True}],
        }
        items = self._persist(spider, raw, "whey-protein")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "dark_lab"
        assert item.source_page is not None
        assert item.source_page.url == "https://www.darklabsuplementos.com.br/products/whey-test"
        assert item.offer.category == "whey-protein"

    def test_vtex_passes_store_page_and_category_and_rejects_bad_payload(self) -> None:
        """VTEX wiring persists its configured store and source page."""
        spider = BlackSkullSpider()
        assert self._persist(spider, {"productId": "bad", "linkText": "", "items": []}, "proteina") == []
        assert ScrapedItem.objects.count() == 0
        raw = {
            "productId": "vtex-product-1",
            "productName": "Whey Test",
            "linkText": "whey-test",
            "items": [{"itemId": "vtex-item-1", "sellers": [{"sellerDefault": True, "commertialOffer": {"Price": "10.00", "AvailableQuantity": 2}}]}],
        }
        items = self._persist(spider, raw, "proteina")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "black_skull"
        assert item.source_page is not None
        assert item.source_page.url == "https://www.blackskullusa.com.br/whey-test/p"
        assert item.offer.category == "proteina"

    def test_nuvemshop_passes_store_page_and_category_and_rejects_bad_payload(self) -> None:
        """Nuvemshop wiring persists its configured store and source page."""
        spider = DuxSpider()
        assert self._persist(spider, {"sku": "bad", "offers": {"url": "", "price": "N/A"}}, "produtos") == []
        assert ScrapedItem.objects.count() == 0
        raw = {
            "@type": "Product",
            "name": "Whey Test",
            "sku": "nuvem-sku-1",
            "offers": {"url": "https://duxhumanhealth.com/produtos/whey-test/?ref=listing", "price": "10.00", "availability": "InStock"},
        }
        items = self._persist(spider, raw, "produtos")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "dux_nutrition"
        assert item.source_page is not None
        assert item.source_page.url == "https://duxhumanhealth.com/produtos/whey-test/"
        assert item.offer.category == "produtos"

    def test_wapstore_passes_store_page_and_category_and_rejects_bad_payload(self) -> None:
        """Wap.Store wiring persists its configured store and source page."""
        spider = GrowthSpider()
        assert self._persist(spider, {"id": "bad", "nome": "Bad", "link": "", "precos": {"por": "N/A"}}, "/proteina/") == []
        assert ScrapedItem.objects.count() == 0
        raw = {"id": "wap-item-1", "nome": "Whey Test", "link": "/whey-test", "precos": {"por": "10.00"}}
        items = self._persist(spider, raw, "/proteina/")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "growth"
        assert item.source_page is not None
        assert item.source_page.url == "https://www.gsuplementos.com.br/whey-test"
        assert item.offer.category == "/proteina/"


class ScrapyRequiredBehaviorTests(SimpleTestCase):
    """Regression tests for behaviors that were previously in HttpClient."""

    def test_impersonation_rotates_after_forbidden_response(self) -> None:
        """403 retries advance to the next browser identity."""
        middleware = ImpersonationMiddleware()
        spider = MagicMock(_impersonation_index=0)
        request = Request("https://example.com")
        response = TextResponse(request.url, status=403, request=request)
        retry = request.replace()
        with patch("scrapers.crawler.middlewares.get_retry_request", return_value=retry):
            result = middleware.process_response(request, response, spider)
        assert result is retry
        assert result.meta["impersonate"] == "chrome119"

    def test_200_waf_page_uses_the_same_retry_rotation(self) -> None:
        """A WAF challenge served with 200 is retried as a block."""
        middleware = ImpersonationMiddleware()
        spider = MagicMock(_impersonation_index=0)
        request = Request("https://example.com")
        response = TextResponse(request.url, body=b"Attention Required! | Cloudflare", request=request)
        retry = request.replace()
        with patch("scrapers.crawler.middlewares.get_retry_request", return_value=retry):
            result = middleware.process_response(request, response, spider)
        assert result is retry
        assert result.meta["impersonate"] == "chrome119"

    def test_retry_after_http_date_is_parsed(self) -> None:
        """Retry-After HTTP dates are converted into a bounded delay."""
        request = Request("https://example.com")
        response = TextResponse(
            request.url,
            status=429,
            headers={"Retry-After": format_datetime(datetime.now(UTC) + timedelta(seconds=20), usegmt=True)},
            request=request,
        )
        wait = parse_retry_after(response)
        assert wait is not None
        assert 0 < wait <= 20

    def test_startup_jitter_is_applied_before_full_run(self) -> None:
        """A full run awaits its randomized startup delay."""
        spider = _DummyCatalogSpider()

        async def collect() -> list[Request]:
            return [request async for request in spider.start()]

        with (
            patch("scrapers.crawler.base.random.uniform", return_value=2.0),
            patch("scrapers.crawler.base.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            requests = asyncio.run(collect())
        sleep.assert_awaited_once_with(2.0)
        assert requests[0].url == "https://dummy.example.com/categories"

    def test_fallback_categories_are_used_after_discovery_failure(self) -> None:
        """The shared scheduler emits configured categories after an empty result."""
        spider = _DummyCatalogSpider()
        requests = list(spider.requests_for_categories([]))
        assert [request.url.rsplit("/", maxsplit=1)[-1] for request in requests] == ["fallback-a", "fallback-b"]

    def test_product_id_deduplication_spans_categories(self) -> None:
        """The same product id in two categories yields one page item."""
        spider = DarkLabSpider()
        raw = {"id": "product-1", "handle": "whey", "title": "Whey", "variants": [{"id": "variant-1", "price": "10", "available": True}]}
        first = list(spider.emit_products([raw], "whey"))
        second = list(spider.emit_products([raw], "kits"))
        assert len(first) == 1
        assert second == []

    def test_price_units_keep_soldiers_cents_and_dark_lab_reais(self) -> None:
        """Only the Soldiers Shopify endpoint interprets integer cents."""
        from scrapers.normalizers.shopify import ShopifyNormalizer

        cents = ShopifyNormalizer(price_int_is_cents=True, price_digit_str_is_cents=True)
        assert cents.parse_price(12990) == 129.90
        assert DarkLabSpider.normalizer.parse_price(12990) == 12990.0
