"""Tests for platform normalization."""

from __future__ import annotations

import json
from decimal import Decimal

from django.test import SimpleTestCase

from offers.models import StockStatus
from scrapers.stores.growth import GrowthSpider
from scrapers.tests.helpers import (
    ScrapedJsonObject,
    _normalize_spider_item,
)


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

    def test_normalizer_skips_without_valid_url(self) -> None:
        """Skips items when URL is missing/invalid."""
        item = dict(self.base_item)
        item["link"] = ""

        result = _normalize_spider_item(self.spider, item, "/proteina/")

        assert result is None

    def test_normalizer_keeps_unit_without_price_as_unavailable(self) -> None:
        """Keep the unit so yesterday's price does not remain current."""
        item = dict(self.base_item)
        item["precos"] = {"por": "N/A"}

        result = _normalize_spider_item(self.spider, item, "/proteina/")

        assert result is not None
        assert result.offers[0].price is None
        assert result.offers[0].stock_status == StockStatus.OUT_OF_STOCK

    def test_normalizer_keeps_available_on_unknown_stock(self) -> None:
        """Unknown stock should not be forced to out-of-stock."""
        item = dict(self.base_item)
        item["estoque"] = "unknown"

        product = _normalize_spider_item(self.spider, item, "/proteina/")
        assert product is not None

        payload = product.offers[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == StockStatus.AVAILABLE

    def test_parse_price_supports_currency_formats(self) -> None:
        """Parses price tokens from common API payload formats."""
        product = _normalize_spider_item(self.spider, self.base_item, "/proteina/")
        assert product is not None
        assert product.offers[0].price == Decimal("139.90")
        item = dict(self.base_item, precos={"por": "R$ 89.50"})
        product = _normalize_spider_item(self.spider, item, "/proteina/")
        assert product is not None
        assert product.offers[0].price == Decimal("89.50")
        item = dict(self.base_item, precos={"por": "N/A"})
        product = _normalize_spider_item(self.spider, item, "/proteina/")
        assert product is not None
        assert product.offers[0].price is None

    def test_category_path_filter_rejects_non_product_routes(self) -> None:
        """Rejects account/checkout-like paths from dynamic menu."""
        assert not self.spider.is_valid_category_path("/conta/meus-pedidos/")
        assert not self.spider.is_valid_category_path("/checkout/")
        assert self.spider.is_valid_category_path("/proteina/")

    def test_normalizer_builds_api_context(self) -> None:
        """The full source context travels with the normalized page."""
        product = _normalize_spider_item(self.spider, self.base_item, "/proteina/")
        assert product is not None
        context = json.loads(product.api_context)
        assert context["platform"] == "wapstore"
        assert "prices" in context["product"]

    def test_normalizer_keeps_wapstore_unit_literal(self) -> None:
        """Wap.Store has no source selection, and names are not interpreted."""
        item = dict(self.base_item, nome="Kit 2x1kg")
        product = _normalize_spider_item(self.spider, item, "/kits/")
        assert product is not None
        offer = product.offers[0]
        assert product.provider_product_id == "1001"
        assert offer.external_id == "1001"
        assert offer.offer_url == product.page_url
        assert offer.variant_context.provider_product_id == "1001"
        assert offer.variant_context.options == []
        assert offer.variant_context.selection is None
        context_json = offer.variant_context.model_dump_json()
        assert "net_mass" not in context_json
        assert "flavor" not in context_json
        assert "combo" not in context_json
