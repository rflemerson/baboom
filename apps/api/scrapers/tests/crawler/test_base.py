"""Tests for the Scrapy crawling infrastructure."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.crawler.base import CatalogSpider
from scrapers.crawler.middlewares import (
    ImpersonationMiddleware,
    parse_retry_after,
)
from scrapers.normalizers.shopify import ShopifyNormalizer
from scrapers.stores.dark_lab import DarkLabSpider
from scrapers.tests.helpers import EXPECTED_FALLBACK_CATEGORY_COUNT

RETRY_AFTER_SECONDS = 20
SOLDIERS_PRICE_IN_REAIS = 129.90
DARK_LAB_PRICE_IN_REAIS = 12990.0


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

    def test_invalid_first_category_does_not_claim_product_id(self) -> None:
        """A later complete copy of a malformed product remains eligible."""
        spider = _DummyCatalogSpider()
        raw = {
            "id": "same-product",
            "title": "Whey",
            "handle": "whey",
            "variants": [{"id": "unit-1", "price": "10", "available": True}],
        }

        assert spider.process_raw_product({**raw, "handle": ""}, "first") == []
        assert "same-product" not in spider.processed_ids
        assert len(spider.process_raw_product(raw, "second")) == 1
        assert spider.process_raw_product(raw, "third") == []


class ScrapyRequiredBehaviorTests(SimpleTestCase):
    """Regression tests for behaviors that were previously in HttpClient."""

    def test_impersonation_rotates_after_forbidden_response(self) -> None:
        """403 retries advance to the next browser identity."""
        middleware = ImpersonationMiddleware()
        spider = MagicMock(_impersonation_index=0)
        request = Request("https://example.com")
        response = TextResponse(request.url, status=403, request=request)
        retry = request.replace()
        with patch(
            "scrapers.crawler.middlewares.get_retry_request", return_value=retry
        ):
            result = middleware.process_response(request, response, spider)
        assert result is retry
        assert result.meta["impersonate"] == "chrome119"

    def test_200_waf_page_uses_the_same_retry_rotation(self) -> None:
        """A WAF challenge served with 200 is retried as a block."""
        middleware = ImpersonationMiddleware()
        spider = MagicMock(_impersonation_index=0)
        request = Request("https://example.com")
        response = TextResponse(
            request.url, body=b"Attention Required! | Cloudflare", request=request
        )
        retry = request.replace()
        with patch(
            "scrapers.crawler.middlewares.get_retry_request", return_value=retry
        ):
            result = middleware.process_response(request, response, spider)
        assert result is retry
        assert result.meta["impersonate"] == "chrome119"

    def test_retry_after_http_date_is_parsed(self) -> None:
        """Retry-After HTTP dates are converted into a bounded delay."""
        request = Request("https://example.com")
        response = TextResponse(
            request.url,
            status=429,
            headers={
                "Retry-After": format_datetime(
                    datetime.now(UTC) + timedelta(seconds=RETRY_AFTER_SECONDS),
                    usegmt=True,
                )
            },
            request=request,
        )
        wait = parse_retry_after(response)
        assert wait is not None
        assert 0 < wait <= RETRY_AFTER_SECONDS

    def test_a_run_reports_which_store_it_crawled(self) -> None:
        """Without the store slug the task cannot delist units the store dropped."""
        spider = _DummyCatalogSpider(categories="fallback-a")
        spider.crawler = MagicMock()

        async def collect() -> list[Request]:
            return [request async for request in spider.start()]

        asyncio.run(collect())

        spider.crawler.stats.set_value.assert_any_call("scraper/store_slug", "dummy")

    def test_startup_jitter_is_applied_before_full_run(self) -> None:
        """A full run awaits its randomized startup delay."""
        spider = _DummyCatalogSpider()

        async def collect() -> list[Request]:
            return [request async for request in spider.start()]

        with (
            patch("scrapers.crawler.base._jitter.uniform", return_value=2.0),
            patch(
                "scrapers.crawler.base.asyncio.sleep", new_callable=AsyncMock
            ) as sleep,
        ):
            requests = asyncio.run(collect())
        sleep.assert_awaited_once_with(2.0)
        assert requests[0].url == "https://dummy.example.com/categories"

    def test_fallback_categories_are_used_after_discovery_failure(self) -> None:
        """The shared scheduler emits configured categories after an empty result."""
        spider = _DummyCatalogSpider()
        requests = list(spider.requests_for_categories([]))
        assert [request.url.rsplit("/", maxsplit=1)[-1] for request in requests] == [
            "fallback-a",
            "fallback-b",
        ]

    def test_product_id_deduplication_spans_categories(self) -> None:
        """The same product id in two categories yields one page item."""
        spider = DarkLabSpider()
        raw = {
            "id": "product-1",
            "handle": "whey",
            "title": "Whey",
            "variants": [{"id": "variant-1", "price": "10", "available": True}],
        }
        first = list(spider.emit_products([raw], "whey"))
        second = list(spider.emit_products([raw], "kits"))
        assert len(first) == 1
        assert second == []

    def test_price_units_keep_soldiers_cents_and_dark_lab_reais(self) -> None:
        """Only the Soldiers Shopify endpoint interprets integer cents."""
        cents = ShopifyNormalizer(
            price_int_is_cents=True, price_digit_str_is_cents=True
        )
        assert cents.parse_price(12990) == SOLDIERS_PRICE_IN_REAIS
        assert DarkLabSpider.normalizer.parse_price(12990) == DARK_LAB_PRICE_IN_REAIS
