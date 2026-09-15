"""Tests for the persisted GraphQL VTEX spider callbacks."""

from __future__ import annotations

import base64
import json
from operator import attrgetter
from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase
from scrapy import Request
from scrapy.http import TextResponse

from scrapers.contracts import ScrapedProductInput
from scrapers.crawler.spiders.vtex_graphql import (
    PAGE_SIZE,
    VtexGraphqlSpider,
)

GRAPHQL_URL = "https://graphql.example.com/api/graphql"
TREE_URL = "https://graphql.example.com/api/categories"


class _TestVtexGraphqlSpider(VtexGraphqlSpider):
    """Concrete GraphQL spider with test-only endpoint configuration."""

    name = "test-vtex-graphql"
    BRAND_NAME = "Test Brand"
    STORE_SLUG = "test-vtex"
    BASE_URL = "https://graphql.example.com"
    API_ENDPOINT = GRAPHQL_URL
    API_TREE = TREE_URL
    QUERY_HASH = "query-hash"
    FALLBACK_CATEGORIES = ("fallback",)


def _response(
    payload: object,
    *,
    meta: dict[str, object],
    url: str = GRAPHQL_URL,
) -> TextResponse:
    """Build an in-memory JSON response for a GraphQL callback."""
    request = Request(url, meta=meta)
    return TextResponse(
        url,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        request=request,
    )


def _product(product_id: str) -> dict[str, object]:
    """Build the VTEX product shape consumed by the shared normalizer."""
    return {
        "productId": product_id,
        "productName": "Whey Test",
        "linkText": "whey-test",
        "brand": "Test Brand",
        "items": [
            {
                "itemId": f"sku-{product_id}",
                "nameComplete": "Whey Test 1kg",
                "name": "Whey Test 1kg",
                "sellers": [
                    {
                        "sellerDefault": True,
                        "commertialOffer": {
                            "Price": 129.90,
                            "AvailableQuantity": 5,
                        },
                    },
                ],
            },
        ],
    }


class VtexGraphqlSpiderTests(SimpleTestCase):
    """Verify GraphQL discovery, pagination, and response extraction."""

    def setUp(self) -> None:
        """Create a configured GraphQL spider for callback tests."""
        self.spider = _TestVtexGraphqlSpider()

    def test_category_discovery_request_targets_the_tree_endpoint(self) -> None:
        """Discovery starts with the configured tree endpoint and callback."""
        request = self.spider.category_discovery_request()

        assert request.url == TREE_URL
        assert request.callback == attrgetter("_parse_categories")(self.spider)
        assert request.headers["Accept"] == b"application/json"

    def test_category_discovery_schedules_each_slug(self) -> None:
        """A category list becomes one first-page request per slug."""
        response = _response(
            [{"url": "/whey/"}, {"url": "/proteins"}, {"name": "ignored"}],
            meta={},
            url=TREE_URL,
        )

        parse_categories = attrgetter("_parse_categories")(self.spider)
        parse_category = attrgetter("_parse_category")(self.spider)
        requests = list(parse_categories(response))

        assert {request.meta["category"] for request in requests} == {
            "proteins",
            "whey",
        }
        assert all(request.meta["start"] == 0 for request in requests)
        assert all(request.callback == parse_category for request in requests)

    def test_category_page_emits_products_and_next_range_when_full(self) -> None:
        """A full GraphQL range emits every product and requests the next range."""
        products = [_product(f"product-{number}") for number in range(PAGE_SIZE)]
        response = _response(
            {"data": {"productSearch": {"products": products}}},
            meta={"category": "whey", "start": 0},
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        results = list(parse_category(response))

        emitted = [
            result for result in results if isinstance(result, ScrapedProductInput)
        ]
        next_request = results[-1]
        assert len(emitted) == PAGE_SIZE
        assert emitted[0].store_slug == self.spider.STORE_SLUG
        assert emitted[-1].provider_product_id == "product-49"
        assert isinstance(next_request, Request)
        assert next_request.meta == {"category": "whey", "start": PAGE_SIZE}
        assert next_request.callback == parse_category

    def test_last_category_page_does_not_request_another_range(self) -> None:
        """A short GraphQL range ends pagination after its emitted product."""
        response = _response(
            {"data": {"products": [_product("last-product")]}},
            meta={"category": "whey", "start": PAGE_SIZE},
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        results = list(parse_category(response))

        assert len(results) == 1
        assert isinstance(results[0], ScrapedProductInput)
        assert results[0].provider_product_id == "last-product"

    def test_empty_category_page_emits_nothing(self) -> None:
        """An empty GraphQL product list ends without a follow-up request."""
        response = _response(
            {"data": {"productSearch": {"products": []}}},
            meta={"category": "whey", "start": 0},
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        parse_graphql_response = attrgetter("_parse_graphql_response")(self.spider)
        assert list(parse_category(response)) == []
        assert (
            parse_graphql_response(
                {"data": {"productSearch": {"products": []}}},
            )
            == []
        )

    def test_malformed_category_response_emits_nothing(self) -> None:
        """Malformed JSON is treated as an empty GraphQL page."""
        request = Request(GRAPHQL_URL, meta={"category": "whey", "start": 0})
        response = TextResponse(
            GRAPHQL_URL,
            body=b"not-json",
            encoding="utf-8",
            request=request,
        )

        parse_category = attrgetter("_parse_category")(self.spider)
        assert list(parse_category(response)) == []

    def test_malformed_category_discovery_uses_fallback(self) -> None:
        """Malformed category JSON schedules the configured fallback category."""
        request = Request(TREE_URL, meta={})
        response = TextResponse(
            TREE_URL,
            body=b"not-json",
            encoding="utf-8",
            request=request,
        )

        parse_categories = attrgetter("_parse_categories")(self.spider)

        requests = list(parse_categories(response))

        assert [item.meta["category"] for item in requests] == ["fallback"]

    def test_supported_graphql_shapes_and_query_variables_are_decoded(self) -> None:
        """The spider accepts all supported product envelopes and query variables."""
        product = _product("product-1")
        parse_graphql_response = attrgetter("_parse_graphql_response")(self.spider)
        assert parse_graphql_response(
            {"data": {"productSearch": {"products": [product]}}},
        ) == [product]
        assert parse_graphql_response(
            {"data": {"products": [product]}},
        ) == [product]
        assert parse_graphql_response(
            {"data": {"products": {"products": [product]}}},
        ) == [product]
        assert parse_graphql_response({"data": {}}) == []
        assert parse_graphql_response({"data": []}) == []

        request = self.spider.category_request("whey")
        query = parse_qs(urlsplit(request.url).query)
        extensions = json.loads(query["extensions"][0])
        variables = json.loads(
            base64.b64decode(extensions["variables"]).decode(),
        )

        assert variables["category"] == "whey"
        assert variables["from"] == 0
        assert variables["to"] == PAGE_SIZE - 1
        assert extensions["persistedQuery"]["sha256Hash"] == "query-hash"
