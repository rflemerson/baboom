"""Tests for Shopify collection, listing, and detail callbacks."""

from __future__ import annotations

import json
from operator import attrgetter
from types import SimpleNamespace

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.contracts import ScrapedProductInput
from scrapers.crawler.spiders.shopify import (
    SHOPIFY_PAGE_SIZE,
    ShopifyApiSpider,
)

SHOPIFY_URL = "https://shopify.example.com"
COLLECTIONS_URL = f"{SHOPIFY_URL}/collections.json"
NEXT_COLLECTION_PAGE = 2


class _TestShopifySpider(ShopifyApiSpider):
    """Concrete Shopify spider with test-only store settings."""

    name = "test-shopify"
    BRAND_NAME = "Test Brand"
    STORE_SLUG = "test-shopify"
    BASE_URL = SHOPIFY_URL
    FALLBACK_CATEGORIES = ("fallback",)


class _TestShopifyDetailSpider(_TestShopifySpider):
    """Shopify test spider configured to request product details."""

    name = "test-shopify-detail"
    USE_PRODUCT_DETAIL = True


def _response(
    payload: object,
    *,
    meta: dict[str, object],
    url: str = COLLECTIONS_URL,
) -> TextResponse:
    """Build an in-memory Shopify JSON response."""
    request = Request(url, meta=meta)
    return TextResponse(
        url,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        request=request,
    )


def _product(product_id: str, *, handle: str | None = None) -> dict[str, object]:
    """Build the Shopify listing shape consumed by its normalizer."""
    resolved_handle = handle or f"whey-{product_id}"
    return {
        "id": product_id,
        "title": "Whey Test",
        "handle": resolved_handle,
        "vendor": "Test Brand",
        "product_type": "Whey",
        "variants": [
            {
                "id": f"variant-{product_id}",
                "title": "1kg",
                "price": "129.90",
                "available": True,
            },
        ],
    }


class ShopifySpiderTests(SimpleTestCase):
    """Verify Shopify discovery, pagination, and detail fallbacks."""

    def setUp(self) -> None:
        """Create a Shopify spider for callback tests."""
        self.spider = _TestShopifySpider()

    def test_category_request_contains_collection_page_parameters(self) -> None:
        """A category request targets Shopify's first paginated product page."""
        request = self.spider.category_request("whey")

        assert request.url == (
            f"{SHOPIFY_URL}/collections/whey/products.json?page=1&limit=250"
        )
        assert request.callback == attrgetter("_parse_category")(self.spider)
        assert request.headers["Accept"] == b"application/json"
        assert request.meta == {"category": "whey", "page": 1}
        assert request.dont_filter is False

    def test_full_collection_page_requests_the_next_discovery_page(self) -> None:
        """A full collection page is paginated while preserving collected handles."""
        collections = [
            {"handle": f"collection-{number}"} for number in range(SHOPIFY_PAGE_SIZE)
        ]
        response = _response(
            {"collections": collections},
            meta={"collection_page": 1, "collection_handles": ["previous"]},
        )

        parse_collections = attrgetter("_parse_collections")(self.spider)
        results = list(parse_collections(response))

        assert len(results) == 1
        request = results[0]
        assert isinstance(request, Request)
        assert request.url.endswith("/collections.json?page=2&limit=250")
        assert request.dont_filter is True
        assert request.meta["collection_page"] == NEXT_COLLECTION_PAGE
        handles = request.meta["collection_handles"]
        assert isinstance(handles, list)
        assert set(handles) == {
            "previous",
            *[f"collection-{n}" for n in range(SHOPIFY_PAGE_SIZE)],
        }

    def test_final_collection_page_schedules_discovered_categories(self) -> None:
        """A short collection page schedules each valid discovered handle."""
        response = _response(
            {"collections": [{"handle": "whey"}, {"title": "ignored"}]},
            meta={"collection_page": 2, "collection_handles": ["previous"]},
        )

        parse_collections = attrgetter("_parse_collections")(self.spider)
        requests = list(parse_collections(response))

        assert {request.meta["category"] for request in requests} == {
            "previous",
            "whey",
        }
        assert all(request.meta["page"] == 1 for request in requests)

    def test_malformed_collection_response_uses_fallback_categories(self) -> None:
        """Malformed collection JSON falls back to the configured category list."""
        request = Request(
            COLLECTIONS_URL,
            meta={"collection_page": 1, "collection_handles": []},
        )
        response = TextResponse(
            COLLECTIONS_URL,
            body=b"not-json",
            encoding="utf-8",
            request=request,
        )

        parse_collections = attrgetter("_parse_collections")(self.spider)
        requests = list(parse_collections(response))

        assert len(requests) == 1
        assert requests[0].meta["category"] == "fallback"

    def test_full_category_page_emits_products_and_next_page(self) -> None:
        """A full Shopify listing emits every product and requests the next page."""
        products = [
            _product(f"product-{number}") for number in range(SHOPIFY_PAGE_SIZE)
        ]
        response = _response(
            {"products": products},
            meta={"category": "whey", "page": 1},
            url=f"{SHOPIFY_URL}/collections/whey/products.json?old=1",
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        results = list(parse_category(response))

        emitted = [
            result for result in results if isinstance(result, ScrapedProductInput)
        ]
        next_request = results[-1]
        assert len(emitted) == SHOPIFY_PAGE_SIZE
        assert emitted[0].provider_product_id == "product-0"
        assert isinstance(next_request, Request)
        assert next_request.url.endswith("/products.json?page=2&limit=250")
        assert next_request.meta == {"category": "whey", "page": 2}

    def test_short_or_empty_category_page_does_not_paginate(self) -> None:
        """A short Shopify page emits its products without a follow-up request."""
        response = _response(
            {"products": [_product("last-product")]},
            meta={"category": "whey", "page": 3},
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        results = list(parse_category(response))

        assert len(results) == 1
        assert isinstance(results[0], ScrapedProductInput)

        empty_response = _response(
            {"products": []},
            meta={"category": "whey", "page": 4},
        )
        assert list(parse_category(empty_response)) == []

    def test_malformed_category_response_emits_nothing(self) -> None:
        """Malformed Shopify JSON is treated as an empty category page."""
        request = Request(
            f"{SHOPIFY_URL}/collections/whey/products.json",
            meta={"category": "whey", "page": 1},
        )
        response = TextResponse(
            request.url,
            body=b"not-json",
            encoding="utf-8",
            request=request,
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        assert list(parse_category(response)) == []

    def test_invalid_listing_entries_and_duplicate_ids_are_skipped(self) -> None:
        """Invalid and already processed Shopify listings produce no item."""
        product = _product("product-1")
        self.spider.processed_ids.add("product-1")
        response = _response(
            {"products": [None, product]},
            meta={"category": "whey", "page": 1},
        )

        parse_category = attrgetter("_parse_category")(self.spider)

        assert list(parse_category(response)) == []

    def test_non_list_product_container_is_ignored(self) -> None:
        """A Shopify product container with the wrong type emits no products."""
        emit_products = attrgetter("_emit_category_products")(self.spider)

        assert list(emit_products((_product("product-1"),), "whey")) == []


class ShopifyDetailSpiderTests(SimpleTestCase):
    """Verify optional Shopify detail requests and their fallbacks."""

    def setUp(self) -> None:
        """Create a detail-enabled Shopify spider and listing fixture."""
        self.spider = _TestShopifyDetailSpider()
        self.listing = _product("product-1", handle="whey-test")

    def test_listing_page_schedules_detail_request(self) -> None:
        """Detail mode claims a listing and schedules its JavaScript endpoint."""
        response = _response(
            {"products": [self.listing]},
            meta={"category": "whey", "page": 1},
            url=f"{SHOPIFY_URL}/collections/whey/products.json",
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        results = list(parse_category(response))

        assert len(results) == 1
        request = results[0]
        assert isinstance(request, Request)
        assert request.url == f"{SHOPIFY_URL}/products/whey-test.js"
        assert request.callback == attrgetter("_parse_detail")(self.spider)
        assert request.errback == attrgetter("_detail_failed")(self.spider)
        assert request.dont_filter is True
        assert request.meta == {
            "listing_product": self.listing,
            "category": "whey",
        }
        assert self.spider.processed_ids == {"product-1"}

    def test_detail_response_emits_the_detail_product(self) -> None:
        """A valid detail response replaces the listing data for normalization."""
        detail = dict(self.listing, title="Whey Detail")
        response = _response(
            detail,
            meta={"listing_product": self.listing, "category": "whey"},
            url=f"{SHOPIFY_URL}/products/whey-test.js",
        )

        parse_detail = attrgetter("_parse_detail")(self.spider)
        results = list(parse_detail(response))

        assert len(results) == 1
        assert isinstance(results[0], ScrapedProductInput)
        assert results[0].offers[0].name == "Whey Detail - 1kg"

    def test_invalid_detail_response_falls_back_to_listing(self) -> None:
        """A detail JSON failure keeps the original listing product usable."""
        request = Request(
            f"{SHOPIFY_URL}/products/whey-test.js",
            meta={"listing_product": self.listing, "category": "whey"},
        )
        response = TextResponse(
            request.url,
            body=b"not-json",
            encoding="utf-8",
            request=request,
        )

        parse_detail = attrgetter("_parse_detail")(self.spider)
        results = list(parse_detail(response))

        assert len(results) == 1
        assert isinstance(results[0], ScrapedProductInput)
        assert results[0].offers[0].name == "Whey Test - 1kg"

    def test_failed_detail_request_falls_back_to_listing(self) -> None:
        """A transport failure still emits the listing product."""
        request = Request(
            f"{SHOPIFY_URL}/products/whey-test.js",
            meta={"listing_product": self.listing, "category": "whey"},
        )
        failure = SimpleNamespace(request=request)

        detail_failed = attrgetter("_detail_failed")(self.spider)
        results = list(detail_failed(failure))

        assert len(results) == 1
        assert isinstance(results[0], ScrapedProductInput)
        assert results[0].provider_product_id == "product-1"

    def test_detail_failure_without_a_request_emits_nothing(self) -> None:
        """A failure without its originating request has no listing to recover."""
        detail_failed = attrgetter("_detail_failed")(self.spider)

        assert list(detail_failed(SimpleNamespace())) == []

    def test_detail_failure_with_an_invalid_listing_emits_nothing(self) -> None:
        """A failure with a non-dictionary listing cannot be normalized."""
        request = Request(
            f"{SHOPIFY_URL}/products/whey-test.js",
            meta={"listing_product": "invalid", "category": "whey"},
        )
        detail_failed = attrgetter("_detail_failed")(self.spider)

        assert list(detail_failed(SimpleNamespace(request=request))) == []
