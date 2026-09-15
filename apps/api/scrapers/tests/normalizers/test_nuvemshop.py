"""Tests for platform normalization."""

from __future__ import annotations

import json
from typing import cast

from django.test import SimpleTestCase

from offers.models import StockStatus
from scrapers.stores.dux import DuxSpider
from scrapers.tests.helpers import (
    DUX_EXPECTED_STOCK,
    ScrapedJsonObject,
    _normalize_spider_item,
)


class DuxNuvemshopSpiderUnitTests(SimpleTestCase):
    """Unit tests for the Nuvemshop JSON-LD ingestion used by Dux."""

    LISTING_HTML = """
    <html><head>
      <script type="application/ld+json">
      {"@type": "Organization", "name": "Dux"}
      </script>
      <script type="application/ld+json">
      {"@type": "Product", "name": "Whey Protein Concentrado - Pote 900g",
       "sku": "410713009", "gtin13": "7898604470045",
       "offers": {"@type": "Offer",
         "url": "https://duxhumanhealth.com/produtos/whey-concentrado-900g/",
         "priceCurrency": "BRL", "price": "159.90",
         "availability": "http://schema.org/InStock",
         "inventoryLevel": {"@type": "QuantitativeValue", "value": "42"}}}
      </script>
      <script type="application/ld+json">not json at all</script>
    </head></html>
    """

    def setUp(self) -> None:
        """Create the spider and a reusable JSON-LD product entry."""
        self.spider = DuxSpider()
        self.base_item: ScrapedJsonObject = {
            "@type": "Product",
            "name": "Whey Protein Concentrado - Pote 900g",
            "sku": "410713009",
            "gtin13": "7898604470045",
            "offers": {
                "@type": "Offer",
                "url": "https://duxhumanhealth.com/produtos/whey-900g/",
                "price": "159.90",
                "availability": "http://schema.org/InStock",
                "inventoryLevel": {"value": "42"},
            },
        }

    def test_extract_products_keeps_only_product_blocks(self) -> None:
        """Organization blocks and malformed JSON must not become products."""
        products = self.spider.extract_products(self.LISTING_HTML)

        assert len(products) == 1
        assert products[0]["sku"] == "410713009"

    def test_normalizer_maps_offer_fields(self) -> None:
        """Price, stock and identifiers come from the embedded offer."""
        result = _normalize_spider_item(self.spider, self.base_item, "produtos")

        assert result is not None
        payload = result.offers[0]
        assert payload.external_id == "410713009"
        assert payload.ean == "7898604470045"
        assert payload.stock_quantity == DUX_EXPECTED_STOCK
        assert payload.stock_status == StockStatus.AVAILABLE
        assert result.page_url == "https://duxhumanhealth.com/produtos/whey-900g/"

    def test_out_of_stock_offer_zeroes_quantity(self) -> None:
        """An unavailable offer is stored as out of stock with no units."""
        item = dict(self.base_item)
        item["offers"] = dict(
            cast("ScrapedJsonObject", self.base_item["offers"]),
            availability="http://schema.org/OutOfStock",
        )

        result = _normalize_spider_item(self.spider, item, "produtos")
        assert result is not None

        payload = result.offers[0]
        assert payload.stock_status == StockStatus.OUT_OF_STOCK
        assert payload.stock_quantity == 0

    def test_normalizer_skips_item_without_sku(self) -> None:
        """The SKU is the external identifier, so an entry without one is skipped."""
        item = dict(self.base_item)
        item["sku"] = ""

        result = _normalize_spider_item(self.spider, item, "produtos")

        assert result is None

    def test_normalizer_keeps_unit_without_price_as_unavailable(self) -> None:
        """Missing listing price must not leave an old offer available."""
        item = dict(self.base_item)
        item["offers"] = dict(
            cast("ScrapedJsonObject", self.base_item["offers"]),
            price="sob consulta",
        )

        result = _normalize_spider_item(self.spider, item, "produtos")

        assert result is not None
        assert result.offers[0].price is None
        assert result.offers[0].stock_status == StockStatus.OUT_OF_STOCK

    def test_normalizer_builds_api_context(self) -> None:
        """The full JSON-LD entry is handed downstream as the api context."""
        product = _normalize_spider_item(self.spider, self.base_item, "produtos")
        assert product is not None

        context = json.loads(product.api_context)
        assert context["platform"] == "nuvemshop"
        assert context["product"]["sku"] == "410713009"

    def test_normalizer_does_not_invent_an_addressable_variant(self) -> None:
        """Listing JSON-LD leaves variant selection absent, even for kits."""
        item = dict(self.base_item, name="Kit 2x1kg")
        product = _normalize_spider_item(self.spider, item, "produtos")
        assert product is not None
        offer = product.offers[0]
        assert product.page_url == offer.offer_url
        assert offer.variant_context.options == []
        assert offer.variant_context.selection is None
        context_json = offer.variant_context.model_dump_json()
        assert "net_mass" not in context_json
        assert "flavor" not in context_json
        assert "combo" not in context_json
