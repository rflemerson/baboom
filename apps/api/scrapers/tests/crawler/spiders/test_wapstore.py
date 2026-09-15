"""Tests for Wap.Store menu and offset pagination callbacks."""

from __future__ import annotations

import json
import os
from operator import attrgetter
from unittest.mock import patch

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.contracts import ScrapedProductInput
from scrapers.crawler.spiders.wapstore import (
    PAGE_SIZE,
    WapStoreApiSpider,
)

WAPSTORE_URL = "https://wapstore.example.com"
LISTING_URL = f"{WAPSTORE_URL}/api/products"
MENU_URL = f"{WAPSTORE_URL}/api/menu"


class _TestWapStoreSpider(WapStoreApiSpider):
    """Concrete Wap.Store spider with test-only endpoint configuration."""

    name = "test-wapstore"
    BRAND_NAME = "Test Brand"
    STORE_SLUG = "test-wapstore"
    BASE_URL = WAPSTORE_URL
    API_LISTING = LISTING_URL
    API_MENU = MENU_URL
    FALLBACK_CATEGORIES = ("/fallback/",)


def _response(
    payload: object,
    *,
    meta: dict[str, object],
    url: str = LISTING_URL,
    status: int = 200,
) -> TextResponse:
    """Build an in-memory Wap.Store JSON response."""
    request = Request(url, meta=meta)
    return TextResponse(
        url,
        status=status,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        request=request,
    )


def _product(product_id: str) -> dict[str, object]:
    """Build the listing shape consumed by the Wap.Store normalizer."""
    return {
        "id": product_id,
        "nome": "Whey Test",
        "sku": f"SKU-{product_id}",
        "link": f"/whey-{product_id}",
        "precos": {"por": "129,90"},
        "estoque": 5,
    }


class WapStoreSpiderTests(SimpleTestCase):
    """Verify Wap.Store menu discovery, TLS settings, and pagination."""

    def test_tls_verification_follows_the_opt_in_environment_setting(self) -> None:
        """The crawler verifies TLS only when the existing flag is enabled."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GROWTH_SSL_VERIFY", None)
            default_spider = _TestWapStoreSpider()
        with patch.dict(os.environ, {"GROWTH_SSL_VERIFY": "1"}):
            verified_spider = _TestWapStoreSpider()

        api_meta = attrgetter("_api_meta")
        assert api_meta(default_spider)() == {"impersonate_args": {"verify": False}}
        assert api_meta(verified_spider)() == {"impersonate_args": {"verify": True}}

    def test_initial_requests_include_api_headers_and_tls_meta(self) -> None:
        """Discovery and listing requests carry the Wap.Store transport policy."""
        spider = _TestWapStoreSpider(categories="/proteina/")

        discovery = spider.category_discovery_request()
        category = spider.category_request("/proteina/")

        assert discovery.url == MENU_URL
        assert discovery.headers["app-token"] == b"wapstore"
        assert discovery.meta == {"impersonate_args": {"verify": False}}
        assert category.url.endswith("?url=%2Fproteina%2F&offset=0&limit=30")
        assert category.meta == {
            "impersonate_args": {"verify": False},
            "category": "/proteina/",
            "offset": 0,
        }

    def test_nested_menu_paths_schedule_only_valid_categories(self) -> None:
        """Nested menu links are flattened while policy routes are filtered."""
        response = _response(
            {
                "data": [
                    {
                        "url": "/proteina/",
                        "children": [
                            {"link": "/creatina/"},
                            {"url": "/blog/not-a-category/"},
                        ],
                    },
                    {"url": f"{WAPSTORE_URL}/checkout/"},
                    {"itens": [{"url": "/vitaminas"}]},
                    {"url": "minerais", "children": "not-a-list"},
                    "invalid",
                ],
            },
            meta={},
            url=MENU_URL,
        )

        parse_menu = attrgetter("_parse_menu")(_TestWapStoreSpider())
        requests = list(parse_menu(response))

        assert {request.meta["category"] for request in requests} == {
            "/creatina/",
            "/minerais/",
            "/proteina/",
            "/vitaminas/",
        }

    def test_failed_or_malformed_menu_uses_fallback_categories(self) -> None:
        """A menu failure never leaves the crawler without configured categories."""
        spider = _TestWapStoreSpider()
        parse_menu = attrgetter("_parse_menu")(spider)

        failed = list(
            parse_menu(
                _response(
                    {},
                    meta={},
                    url=MENU_URL,
                    status=503,
                ),
            ),
        )
        malformed_request = Request(MENU_URL, meta={})
        malformed = TextResponse(
            MENU_URL,
            body=b"not-json",
            encoding="utf-8",
            request=malformed_request,
        )
        malformed_results = list(parse_menu(malformed))

        assert [request.meta["category"] for request in failed] == ["/fallback/"]
        assert [request.meta["category"] for request in malformed_results] == [
            "/fallback/",
        ]

    def test_full_category_page_emits_products_and_next_offset(self) -> None:
        """A full Wap.Store page emits products and requests the next offset."""
        products = [_product(f"product-{number}") for number in range(PAGE_SIZE)]
        response = _response(
            {"conteudo": {"produtos": products}},
            meta={"category": "/proteina/", "offset": 0},
        )

        parse_category = attrgetter("_parse_category")(_TestWapStoreSpider())
        results = list(parse_category(response))

        emitted = [
            result for result in results if isinstance(result, ScrapedProductInput)
        ]
        next_request = results[-1]
        assert len(emitted) == PAGE_SIZE
        assert emitted[0].provider_product_id == "product-0"
        assert isinstance(next_request, Request)
        assert next_request.url.endswith(
            "?url=%2Fproteina%2F&offset=30&limit=30",
        )
        assert next_request.meta == {
            "impersonate_args": {"verify": False},
            "category": "/proteina/",
            "offset": PAGE_SIZE,
        }
        assert next_request.dont_filter is True

    def test_short_empty_or_failed_category_page_stops_without_request(self) -> None:
        """Short, empty, and failed Wap.Store pages do not paginate."""
        spider = _TestWapStoreSpider()
        parse_category = attrgetter("_parse_category")(spider)
        meta = {"category": "/proteina/", "offset": PAGE_SIZE}

        short = list(
            parse_category(
                _response(
                    {"data": {"list": [_product("last-product")]}},
                    meta=meta,
                ),
            ),
        )
        empty = list(
            parse_category(
                _response({"conteudo": {"produtos": []}}, meta=meta),
            ),
        )
        failed = list(
            parse_category(
                _response({}, meta=meta, status=404),
            ),
        )

        assert len(short) == 1
        assert isinstance(short[0], ScrapedProductInput)
        assert empty == []
        assert failed == []

        invalid_envelope = list(
            parse_category(
                _response({"other": []}, meta=meta),
            ),
        )
        assert invalid_envelope == []
        extract_products = attrgetter("_extract_products_list")(spider)
        assert extract_products({"other": []}) == []

    def test_malformed_category_response_emits_nothing(self) -> None:
        """Malformed Wap.Store listing JSON is treated as an empty page."""
        request = Request(
            LISTING_URL,
            meta={"category": "/proteina/", "offset": 0},
        )
        response = TextResponse(
            LISTING_URL,
            body=b"not-json",
            encoding="utf-8",
            request=request,
        )

        parse_category = attrgetter("_parse_category")(_TestWapStoreSpider())
        assert list(parse_category(response)) == []
