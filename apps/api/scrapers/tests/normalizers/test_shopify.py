"""Tests for platform normalization."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import cast

from django.test import SimpleTestCase

from offers.models import StockStatus
from scrapers.contracts import VariantOption
from scrapers.crawler.spiders.shopify import ShopifyApiSpider
from scrapers.stores.dark_lab import DarkLabSpider
from scrapers.stores.integral_medica import IntegralMedicaSpider
from scrapers.stores.soldiers import SoldiersSpider
from scrapers.tests.helpers import (
    EXPECTED_COMMA_DECIMAL_PRICE,
    EXPECTED_SHOPIFY_JS_PRICE,
    ScrapedJsonObject,
    _normalize_spider_item,
)


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

    def test_normalizer_skips_item_without_handle(self) -> None:
        """Should skip item when Shopify handle is missing."""
        item = dict(self.base_item)
        item["handle"] = ""

        result = _normalize_spider_item(self.spider, item, "whey-protein")

        assert result is None

    def test_normalizer_keeps_variant_without_price_as_unavailable(self) -> None:
        """A missing price must clear the previous sellable snapshot."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], price="N/A")]

        result = _normalize_spider_item(self.spider, item, "whey-protein")

        assert result is not None
        assert result.offers[0].price is None
        assert result.offers[0].stock_status == StockStatus.OUT_OF_STOCK

    def test_every_variant_becomes_its_own_offer(self) -> None:
        """A page selling two sizes sells two things, at two prices."""
        item = dict(self.base_item)
        item["variants"] = [
            {
                "id": 111,
                "title": "1kg",
                "sku": "WHEY-1KG",
                "price": "129.90",
                "available": True,
                "inventory_quantity": 7,
            },
            {
                "id": 222,
                "title": "2kg",
                "sku": "WHEY-2KG",
                "price": "229.90",
                "available": True,
                "inventory_quantity": 3,
            },
        ]

        product = _normalize_spider_item(self.spider, item, "whey-protein")
        assert product is not None

        sent = product.offers
        assert [entry.external_id for entry in sent] == ["111", "222"]
        assert [entry.price for entry in sent] == [
            Decimal("129.90"),
            Decimal("229.90"),
        ]

    def test_identity_is_the_variant_not_the_product(self) -> None:
        """The row that carries a variant's price must be named for it.

        Identifying the offer by the product while pricing it from whichever
        variant happened to be in stock let one row's price history span two
        different things.
        """
        product = _normalize_spider_item(self.spider, self.base_item, "whey-protein")
        assert product is not None

        sent = product.offers[0]
        assert sent.external_id == "111"
        assert product.provider_product_id == "123"
        assert sent.sku == "WHEY-CHOCO"

    def test_a_sold_out_variant_is_still_recorded(self) -> None:
        """Out of stock is a fact about an offer, not a reason to drop it."""
        item = dict(self.base_item)
        item["variants"] = [
            {"id": 111, "title": "1kg", "price": "129.90", "available": False},
        ]

        product = _normalize_spider_item(self.spider, item, "whey-protein")
        assert product is not None

        sent = product.offers[0]
        assert sent.stock_status == StockStatus.OUT_OF_STOCK
        assert sent.stock_quantity == 0

    def test_the_offer_name_says_which_variant_it_is(self) -> None:
        """A curator reads the name to tell two offers of a page apart.

        Shopify names the only variant of a plain product "Default Title",
        which distinguishes nothing and does not belong in the name.
        """
        item = dict(self.base_item)
        item["variants"] = [
            {"id": 111, "title": "Chocolate", "price": "1.00", "available": True},
            {"id": 222, "title": "Default Title", "price": "1.00", "available": True},
        ]

        product = _normalize_spider_item(self.spider, item, "whey-protein")
        assert product is not None

        names = [offer.name for offer in product.offers]
        assert names == ["Whey Test - Chocolate", "Whey Test"]

    def test_a_variant_without_an_id_is_skipped(self) -> None:
        """Without a variant id there is nothing stable to call the offer."""
        item = dict(self.base_item)
        item["variants"] = [
            {"title": "1kg", "sku": "WHEY-1KG", "price": "129.90", "available": True},
        ]

        assert _normalize_spider_item(self.spider, item, "whey-protein") is None

    def test_parse_price_handles_comma_decimal(self) -> None:
        """Parses prices with comma decimal separator."""
        value = self.spider.normalizer.parse_price("149,90")
        assert value == EXPECTED_COMMA_DECIMAL_PRICE

    def test_normalizer_builds_api_context(self) -> None:
        """The full source context travels with the normalized page."""
        product = _normalize_spider_item(self.spider, self.base_item, "whey-protein")
        assert product is not None
        context = json.loads(product.api_context)
        assert context["platform"] == "shopify"
        assert "variants" in context
        assert "options" in context

    def test_normalizer_keeps_available_on_unknown_shopify_stock(self) -> None:
        """Available Shopify items without quantity should keep stock unknown."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], inventory_quantity=None)]

        product = _normalize_spider_item(self.spider, item, "whey-protein")
        assert product is not None

        payload = product.offers[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == StockStatus.AVAILABLE

    def test_normalizer_preserves_options_and_does_not_infer_commercial_data(
        self,
    ) -> None:
        """Variant context repeats store labels without interpreting names."""
        item = dict(self.base_item, title="Kit 2x1kg")
        item["options"] = [
            {"name": "Tamanho", "values": ["1kg"]},
            {"name": "Sabor", "values": ["Chocolate"]},
        ]
        item["variants"] = [
            dict(
                cast("ScrapedJsonObject", self.base_item["variants"])[0],
                title="1kg / Chocolate",
                option1="1kg",
                option2="Chocolate",
            ),
        ]

        product = _normalize_spider_item(self.spider, item, "kits")
        assert product is not None
        offer = product.offers[0]
        assert product.page_url == f"{self.spider.BASE_URL}/products/whey-test"
        assert offer.offer_url.endswith("?variant=111")
        assert offer.variant_context.provider_product_id == "123"
        assert offer.variant_context.options == [
            VariantOption(name="Tamanho", value="1kg"),
            VariantOption(name="Sabor", value="Chocolate"),
        ]
        context_json = offer.variant_context.model_dump_json()
        assert "net_mass" not in context_json
        assert "flavor" not in context_json
        assert "combo" not in context_json


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

    def test_collections_request_is_configured_for_category_discovery(self) -> None:
        """Shopify starts with its collections endpoint and page parameters."""
        request = self.spider.category_discovery_request()

        assert request.url.endswith("/collections.json?page=1&limit=250")

    def test_normalizer_skips_without_handle(self) -> None:
        """Skips item when handle is missing."""
        item = dict(self.base_item)
        item["handle"] = ""

        result = _normalize_spider_item(self.spider, item, "barra")

        assert result is None

    def test_normalizer_keeps_variant_without_price_as_unavailable(self) -> None:
        """The Soldiers price format does not make a missing price sellable."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], price="N/A")]

        result = _normalize_spider_item(self.spider, item, "barra")

        assert result is not None
        assert result.offers[0].price is None
        assert result.offers[0].stock_status == StockStatus.OUT_OF_STOCK

    def test_normalizer_keeps_available_on_unknown_shopify_stock(self) -> None:
        """Available Shopify items without quantity should keep stock unknown."""
        item = dict(self.base_item)
        base_variants = cast("list[ScrapedJsonObject]", self.base_item["variants"])
        item["variants"] = [dict(base_variants[0], inventory_quantity=None)]

        product = _normalize_spider_item(self.spider, item, "barra")
        assert product is not None

        payload = product.offers[0]
        assert payload.stock_quantity is None
        assert payload.stock_status == StockStatus.AVAILABLE

    def test_normalizer_builds_api_context(self) -> None:
        """The full source context travels with the normalized page."""
        product = _normalize_spider_item(self.spider, self.base_item, "barra")
        assert product is not None
        context = json.loads(product.api_context)
        assert context["platform"] == "shopify"
        assert "variants" in context
        assert "options" in context

    def test_parse_price_handles_shopify_js_cents(self) -> None:
        """Converts integer cents from product.js into decimal reais."""
        assert self.spider.normalizer.parse_price(1390) == EXPECTED_SHOPIFY_JS_PRICE
        assert self.spider.normalizer.parse_price("1390") == EXPECTED_SHOPIFY_JS_PRICE


class IntegralMedicaSpiderUnitTests(SimpleTestCase):
    """Integralmedica now ingests through the Shopify template."""

    def test_spider_uses_the_shopify_template(self) -> None:
        """The VTEX endpoints are gone, so the spider must be Shopify-based."""
        spider = IntegralMedicaSpider()

        assert isinstance(spider, ShopifyApiSpider)
        assert spider.STORE_SLUG == "integral_medica"
        assert spider.BASE_URL.endswith(".myshopify.com")
