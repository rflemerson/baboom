"""Tests for the legacy VTEX category-tree and search callbacks."""

from __future__ import annotations

import json
from operator import attrgetter

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.contracts import ScrapedProductInput
from scrapers.crawler.spiders.vtex_search import (
    VTEX_PAGE_SIZE,
    VtexSearchSpider,
)

VTEX_URL = "https://vtex.example.com"
TREE_URL = f"{VTEX_URL}/api/category/tree"


class _TestVtexSearchSpider(VtexSearchSpider):
    """Concrete legacy VTEX spider with test-only endpoint configuration."""

    name = "test-vtex-search"
    BRAND_NAME = "Test Brand"
    STORE_SLUG = "test-vtex"
    BASE_URL = VTEX_URL
    API_TREE = TREE_URL
    FALLBACK_CATEGORIES = ("fallback",)


def _response(
    payload: object,
    *,
    meta: dict[str, object],
    url: str = TREE_URL,
    status: int = 200,
) -> TextResponse:
    """Build an in-memory VTEX JSON response."""
    request = Request(url, meta=meta)
    return TextResponse(
        url,
        status=status,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        request=request,
    )


def _product(product_id: str) -> dict[str, object]:
    """Build the product shape consumed by the VTEX normalizer."""
    return {
        "productId": product_id,
        "productName": "Whey Test",
        "linkText": f"whey-{product_id}",
        "items": [
            {
                "itemId": f"sku-{product_id}",
                "nameComplete": "Whey Test 1kg",
                "sellers": [
                    {
                        "sellerDefault": True,
                        "commertialOffer": {
                            "Price": "129,90",
                            "AvailableQuantity": 5,
                        },
                    },
                ],
            },
        ],
    }


class VtexSearchSpiderTests(SimpleTestCase):
    """Verify VTEX category discovery, pagination, and malformed input handling."""

    def setUp(self) -> None:
        """Create a configured legacy VTEX spider."""
        self.spider = _TestVtexSearchSpider()

    def test_category_discovery_request_targets_the_tree_endpoint(self) -> None:
        """Discovery starts with the configured category-tree endpoint."""
        request = self.spider.category_discovery_request()

        assert request.url == TREE_URL
        assert request.callback == attrgetter("_parse_categories")(self.spider)
        assert request.headers["Accept"] == b"application/json"

    def test_category_discovery_flattens_nested_tree_urls(self) -> None:
        """Nested category URLs become unique search requests."""
        response = _response(
            [
                {
                    "url": "/proteina/",
                    "children": [{"url": "/proteina/whey/"}],
                },
                {"name": "ignored"},
                "invalid",
            ],
            meta={},
        )

        parse_categories = attrgetter("_parse_categories")(self.spider)
        requests = list(parse_categories(response))

        assert {request.meta["category"] for request in requests} == {
            "proteina",
            "whey",
        }
        assert all(request.meta["start"] == 0 for request in requests)
        assert all(request.url.startswith(self.spider.BASE_URL) for request in requests)

    def test_failed_or_malformed_category_tree_uses_fallback(self) -> None:
        """A category-tree failure schedules the configured fallback."""
        parse_categories = attrgetter("_parse_categories")(self.spider)
        failed = list(
            parse_categories(
                _response({}, meta={}, status=503),
            ),
        )
        malformed = TextResponse(
            TREE_URL,
            body=b"not-json",
            encoding="utf-8",
            request=Request(TREE_URL, meta={}),
        )
        malformed_results = list(parse_categories(malformed))

        assert [request.meta["category"] for request in failed] == ["fallback"]
        assert [request.meta["category"] for request in malformed_results] == [
            "fallback",
        ]

    def test_category_request_contains_inclusive_range_and_statuses(self) -> None:
        """The first search request uses VTEX's inclusive range convention."""
        request = self.spider.category_request("proteina")

        assert request.url.endswith(
            "/api/catalog_system/pub/products/search/proteina?_from=0&_to=49",
        )
        assert request.meta == {
            "category": "proteina",
            "start": 0,
            "handle_httpstatus_list": [200, 206],
        }

    def test_full_category_page_emits_products_and_next_range(self) -> None:
        """A full VTEX range emits products and requests the next inclusive range."""
        products = [_product(f"product-{number}") for number in range(VTEX_PAGE_SIZE)]
        response = _response(
            products,
            meta={"category": "proteina", "start": 0},
            url=f"{VTEX_URL}/api/search/proteina?old=1",
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        results = list(parse_category(response))

        emitted = [
            result for result in results if isinstance(result, ScrapedProductInput)
        ]
        next_request = results[-1]
        assert len(emitted) == VTEX_PAGE_SIZE
        assert emitted[0].provider_product_id == "product-0"
        assert isinstance(next_request, Request)
        assert next_request.url.endswith("/api/search/proteina?_from=50&_to=99")
        assert next_request.meta == {
            "category": "proteina",
            "start": VTEX_PAGE_SIZE,
            "handle_httpstatus_list": [200, 206],
        }

    def test_short_empty_or_malformed_page_does_not_paginate(self) -> None:
        """Short, empty, and malformed VTEX pages end without another request."""
        spider = self.spider
        parse_category = attrgetter("_parse_category")(spider)
        meta = {"category": "proteina", "start": VTEX_PAGE_SIZE}

        short = list(parse_category(_response([_product("last")], meta=meta)))
        empty = list(parse_category(_response([], meta=meta)))
        malformed = TextResponse(
            f"{VTEX_URL}/api/search/proteina",
            body=b"not-json",
            encoding="utf-8",
            request=Request(
                f"{VTEX_URL}/api/search/proteina",
                meta=meta,
            ),
        )
        malformed_results = list(parse_category(malformed))

        assert len(short) == 1
        assert isinstance(short[0], ScrapedProductInput)
        assert empty == []
        assert malformed_results == []
