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


def _value(
    value_id: int,
    label: str,
    sku: str,
    price: str,
    stock: int,
) -> ScrapedJsonObject:
    """Return one buyable value of a Wap.Store `simples` attribute, as served."""
    return {
        "idAtributoValor": value_id,
        "label": label,
        "sku": sku,
        "precos": {"por": price, "vista": price},
        "estoque": stock,
        "carrinho": {"hash": f"185-{value_id}-0-0-1"},
    }


class GrowthVariantTests(SimpleTestCase):
    """Wap.Store publishes buyable units in two shapes, and both are read.

    ``atributos.simples`` lists the units inside one page, each with its own
    sku, price and stock: flavors on the 1 kg whey, weights on Daily Whey.
    ``atributos.unico`` lists sibling pages, one product id per value, so it
    says which value this page is.
    """

    def setUp(self) -> None:
        """Create the two shapes as the Growth listing serves them."""
        self.spider = GrowthSpider()
        self.whey = {
            "id": 185,
            "nome": "(TOP) Whey Protein Concentrado 1Kg",
            "sku": "33",
            "link": "/whey-protein-concentrado-1kg-growth-supplements-p985936",
            "precos": {"por": 194.33},
            "estoque": 400000,
            "atributos": {
                "simples": {
                    "id": "1",
                    "nome": "Sabor",
                    "valores": [
                        _value(1, "Chocolate", "10003", "194.33", 50800),
                        _value(4, "Natural", "10010", "189.90", 0),
                    ],
                },
            },
        }
        self.daily = {
            "id": 4637,
            "nome": "Daily Whey",
            "adicionalNome": "Doce de Leite",
            "sku": "daily-whey-doce-de-leite",
            "link": "/daily-whey-doce-de-leite",
            "precos": {"por": 111},
            "estoque": 4199,
            "atributos": {
                "unico": {
                    "id": "15",
                    "nome": "Sabor",
                    "valores": [
                        {"label": "Chocolate", "produto": {"id": 4017}},
                        {"label": "Doce de Leite", "produto": {"id": 4637}},
                    ],
                },
                "simples": {
                    "id": "7",
                    "nome": "Peso",
                    "valores": [
                        _value(51, "400 g", "dw-dl-400", "111.00", 4199),
                        _value(52, "800 g", "dw-dl-800", "199.90", 12),
                    ],
                },
            },
        }

    def _offers(self, item: ScrapedJsonObject) -> dict[str, object]:
        """Normalize an item and index its offers by external id."""
        product = _normalize_spider_item(self.spider, item, "/proteina/")
        assert product is not None
        return {offer.external_id: offer for offer in product.offers}

    def test_each_flavor_inside_a_page_is_its_own_offer(self) -> None:
        """Nineteen flavors behind one id are nineteen things to buy, not one."""
        offers = self._offers(self.whey)

        assert set(offers) == {"185-1", "185-4"}
        natural = offers["185-4"]
        assert natural.sku == "10010"
        assert natural.price == Decimal("189.90")
        assert natural.stock_status == StockStatus.OUT_OF_STOCK
        assert natural.variant_context.provider_product_id == "185"
        assert natural.variant_context.options[0].model_dump() == {
            "name": "Sabor",
            "value": "Natural",
        }

    def test_the_page_says_the_unit_is_chosen_in_its_form(self) -> None:
        """The page URL never changes with the flavor; the buyer picks it."""
        natural = self._offers(self.whey)["185-4"]

        assert natural.offer_url.endswith("-p985936")
        assert natural.variant_context.selection is not None
        assert natural.variant_context.selection.kind == "form_option"
        assert natural.variant_context.selection.parameters == {"Sabor": "Natural"}

    def test_a_page_that_is_one_flavor_sells_each_weight_separately(self) -> None:
        """Daily Whey Doce de Leite is one flavor sold in two weights."""
        offers = self._offers(self.daily)

        assert set(offers) == {"4637-51", "4637-52"}
        large = offers["4637-52"]
        assert large.price == Decimal("199.90")
        assert [option.model_dump() for option in large.variant_context.options] == [
            {"name": "Sabor", "value": "Doce de Leite"},
            {"name": "Peso", "value": "800 g"},
        ]

    def test_a_page_lists_all_of_its_units(self) -> None:
        """A unit that leaves the attribute list has left the store's page."""
        product = _normalize_spider_item(self.spider, self.whey, "/proteina/")

        assert product is not None
        assert product.complete_unit_list is True
