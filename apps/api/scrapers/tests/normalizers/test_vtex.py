"""Tests for platform normalization."""

from __future__ import annotations

import json
from decimal import Decimal

from django.test import SimpleTestCase

from offers.models import StockStatus
from scrapers.contracts import VariantOption
from scrapers.crawler.spiders.vtex_search import VtexSearchSpider
from scrapers.stores.blackskull import BlackSkullSpider
from scrapers.tests.helpers import (
    ScrapedJsonObject,
    _normalize_spider_item,
)


class _DummyVtexSpider(VtexSearchSpider):
    """Concrete test double for VtexSearchSpider helper methods."""

    name = "dummy-vtex"
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

    def test_normalizer_skips_without_valid_url(self) -> None:
        """Skips item when linkText is missing."""
        item = dict(self.base_item)
        item["linkText"] = ""

        result = _normalize_spider_item(self.spider, item, "proteina")

        assert result is None

    def test_normalizer_keeps_sku_without_price_as_unavailable(self) -> None:
        """Keep the SKU to clear a stale price and stock status."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["Price"] = "N/A"

        result = _normalize_spider_item(self.spider, item, "proteina")

        assert result is not None
        assert result.offers[0].price is None
        assert result.offers[0].stock_status == StockStatus.OUT_OF_STOCK

    def test_normalizer_keeps_available_on_unknown_stock(self) -> None:
        """Unknown stock should keep item available by default."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = "x"

        product = _normalize_spider_item(self.spider, item, "proteina")
        assert product is not None

        payload = product.offers[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == StockStatus.AVAILABLE

    def test_parse_price_supports_common_formats(self) -> None:
        """Parses decimal strings and rejects invalid price."""
        item = dict(self.base_item)
        item["items"] = [
            dict(
                self.base_item["items"][0],
                sellers=[
                    {
                        "sellerDefault": True,
                        "commertialOffer": {"Price": "99,90", "AvailableQuantity": 7},
                    }
                ],
            ),
        ]
        product = _normalize_spider_item(self.spider, item, "proteina")
        assert product is not None
        assert product.offers[0].price == Decimal("99.90")
        item["items"] = [
            dict(
                item["items"][0],
                sellers=[
                    {
                        "sellerDefault": True,
                        "commertialOffer": {"Price": 55, "AvailableQuantity": 7},
                    }
                ],
            ),
        ]
        product = _normalize_spider_item(self.spider, item, "proteina")
        assert product is not None
        assert product.offers[0].price == Decimal("55.00")
        item["items"] = [
            dict(
                item["items"][0],
                sellers=[
                    {
                        "sellerDefault": True,
                        "commertialOffer": {"Price": "N/A", "AvailableQuantity": 7},
                    }
                ],
            ),
        ]
        product = _normalize_spider_item(self.spider, item, "proteina")
        assert product is not None
        assert product.offers[0].price is None

    def test_normalizer_builds_api_context(self) -> None:
        """The full source context travels with the normalized page."""
        product = _normalize_spider_item(self.spider, self.base_item, "proteina")
        assert product is not None
        context = json.loads(product.api_context)
        assert context["platform"] == "vtex_legacy"
        assert "items" in context

    def test_normalizer_keeps_distinct_skus_and_literal_variations(self) -> None:
        """Each VTEX SKU gets its own URL and its published option order."""
        item = dict(self.base_item)
        item["items"] = [
            {
                "itemId": "SKU-1",
                "name": "Whey 1kg",
                "nameComplete": "Whey 1kg Chocolate",
                "variations": ["Tamanho", "Sabor"],
                "Tamanho": ["1kg"],
                "Sabor": ["Chocolate"],
                "sellers": [
                    {
                        "sellerDefault": True,
                        "commertialOffer": {
                            "Price": "99,90",
                            "AvailableQuantity": 0,
                        },
                    },
                ],
            },
            {
                "itemId": "SKU-2",
                "name": "Whey 2kg",
                "variations": ["Tamanho"],
                "Tamanho": ["2kg"],
                "sellers": [
                    {
                        "commertialOffer": {
                            "Price": "199,90",
                            "AvailableQuantity": 4,
                        },
                    },
                ],
            },
        ]

        product = _normalize_spider_item(self.spider, item, "proteina")
        assert product is not None
        assert [offer.external_id for offer in product.offers] == ["SKU-1", "SKU-2"]
        assert [offer.offer_url for offer in product.offers] == [
            "https://dummy.example.com/vtex-product/p?skuId=SKU-1",
            "https://dummy.example.com/vtex-product/p?skuId=SKU-2",
        ]
        assert product.offers[0].stock_status == StockStatus.OUT_OF_STOCK
        assert product.offers[0].stock_quantity == 0
        assert product.offers[0].variant_context.options == [
            VariantOption(name="Tamanho", value="1kg"),
            VariantOption(name="Sabor", value="Chocolate"),
        ]


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

    def test_normalizer_skips_without_valid_url(self) -> None:
        """Skips item when linkText is missing."""
        item = dict(self.base_item)
        item["linkText"] = ""

        result = _normalize_spider_item(self.spider, item, "proteina")

        assert result is None

    def test_normalizer_keeps_sku_without_price_as_unavailable(self) -> None:
        """Keep the SKU to clear a stale price and stock status."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["Price"] = "N/A"

        result = _normalize_spider_item(self.spider, item, "proteina")

        assert result is not None
        assert result.offers[0].price is None
        assert result.offers[0].stock_status == StockStatus.OUT_OF_STOCK

    def test_normalizer_keeps_available_on_unknown_stock(self) -> None:
        """Unknown stock should keep item available by default."""
        item = dict(self.base_item)
        item["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = "x"

        product = _normalize_spider_item(self.spider, item, "proteina")
        assert product is not None

        payload = product.offers[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == StockStatus.AVAILABLE

    def test_normalizer_builds_api_context(self) -> None:
        """The full source context travels with the normalized page."""
        product = _normalize_spider_item(self.spider, self.base_item, "proteina")
        assert product is not None
        context = json.loads(product.api_context)
        assert context["platform"] == "vtex_legacy"
        assert "items" in context
