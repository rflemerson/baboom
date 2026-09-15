"""Tests for the Scrapy crawling infrastructure."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.crawler.middlewares import (
    MAX_RETRY_AFTER_SECONDS,
    ImpersonationMiddleware,
    is_blocked,
    parse_retry_after,
)

RETRY_AFTER_SECONDS = 20
SOLDIERS_PRICE_IN_REAIS = 129.90
DARK_LAB_PRICE_IN_REAIS = 12990.0
HTTP_OK = 200
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_TOO_MANY_REQUESTS = 429
EXPECTED_RETRY_AFTER_SECONDS = 5.0


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


class ImpersonationMiddlewareTests(SimpleTestCase):
    """Verify retry decisions, Retry-After handling, and identity rotation."""

    def test_request_gets_a_stable_identity_without_overwriting_one(self) -> None:
        """New requests get the first identity while assigned identities persist."""
        middleware = ImpersonationMiddleware()
        spider = SimpleNamespace(name="test-store")
        request = Request("https://example.com")

        middleware.process_request(request, spider)
        assigned = request.meta["impersonate"]
        request.meta["impersonate"] = "custom"
        middleware.process_request(request, spider)

        assert assigned == "chrome120"
        assert request.meta["impersonate"] == "custom"

    def test_non_retryable_response_passes_through_unchanged(self) -> None:
        """Ordinary successful responses do not invoke the retry machinery."""
        middleware = ImpersonationMiddleware()
        spider = SimpleNamespace(name="test-store")
        request = Request("https://example.com")
        response = TextResponse(request.url, status=HTTP_OK, request=request)

        assert middleware.process_response(request, response, spider) is response

    def test_exhausted_retry_returns_the_original_response(self) -> None:
        """When Scrapy refuses another retry, the response remains available."""
        middleware = ImpersonationMiddleware()
        spider = SimpleNamespace(name="test-store")
        request = Request("https://example.com")
        response = TextResponse(
            request.url,
            status=HTTP_SERVICE_UNAVAILABLE,
            request=request,
        )
        with patch(
            "scrapers.crawler.middlewares.get_retry_request",
            return_value=None,
        ):
            result = middleware.process_response(request, response, spider)

        assert result is response

    def test_retry_after_delta_is_delayed_and_rotates_identity(self) -> None:
        """A numeric Retry-After delays a retry after advancing the identity."""
        middleware = ImpersonationMiddleware()
        spider = SimpleNamespace(name="test-store")
        request = Request("https://example.com")
        response = TextResponse(
            request.url,
            status=HTTP_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(int(EXPECTED_RETRY_AFTER_SECONDS))},
            request=request,
        )
        retry = request.replace()
        delayed = object()
        with (
            patch(
                "scrapers.crawler.middlewares.get_retry_request",
                return_value=retry,
            ),
            patch(
                "scrapers.crawler.middlewares.deferLater",
                return_value=delayed,
            ) as defer_later,
        ):
            result = middleware.process_response(request, response, spider)

        assert result is delayed
        assert retry.meta["impersonate"] == "chrome119"
        assert defer_later.call_args.args[1] == EXPECTED_RETRY_AFTER_SECONDS

    def test_invalid_retry_after_is_ignored(self) -> None:
        """An invalid Retry-After header does not delay the retry."""
        request = Request("https://example.com")
        response = TextResponse(
            request.url,
            status=HTTP_TOO_MANY_REQUESTS,
            headers={"Retry-After": "not-a-date"},
            request=request,
        )

        assert parse_retry_after(response) is None

    def test_string_retry_after_delta_is_parsed(self) -> None:
        """A string Retry-After delta is accepted without Scrapy header coercion."""
        response = SimpleNamespace(headers={"Retry-After": "5"})

        assert parse_retry_after(response) == EXPECTED_RETRY_AFTER_SECONDS

    def test_retry_after_parser_returning_none_is_ignored(self) -> None:
        """A parser that returns no date produces no retry delay."""
        response = SimpleNamespace(headers={"Retry-After": "future"})
        with patch(
            "scrapers.crawler.middlewares.parsedate_to_datetime",
            return_value=None,
        ):
            wait = parse_retry_after(response)

        assert wait is None

    def test_naive_retry_after_date_is_treated_as_utc(self) -> None:
        """A date without timezone information is interpreted as UTC."""
        response = SimpleNamespace(headers={"Retry-After": "future"})
        with patch(
            "scrapers.crawler.middlewares.parsedate_to_datetime",
            return_value=datetime.fromisoformat("2099-01-01"),
        ):
            wait = parse_retry_after(response)

        assert wait == MAX_RETRY_AFTER_SECONDS
