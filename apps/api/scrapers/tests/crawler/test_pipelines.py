"""Tests for the Scrapy crawling infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.test import TestCase

from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.models import ScrapedItem
from scrapers.stores.blackskull import BlackSkullSpider
from scrapers.stores.dark_lab import DarkLabSpider
from scrapers.stores.dux import DuxSpider
from scrapers.stores.growth import GrowthSpider

if TYPE_CHECKING:
    from scrapers.crawler.base import CatalogSpider

RETRY_AFTER_SECONDS = 20
SOLDIERS_PRICE_IN_REAIS = 129.90
DARK_LAB_PRICE_IN_REAIS = 12990.0


class ProcessRawProductIntegrationTests(TestCase):
    """Concrete spiders pass configuration through normalization and pipeline."""

    def _persist(self, spider: CatalogSpider, raw: dict, category: str) -> list[object]:
        """Send normalized products through the production pipeline."""
        products = spider.process_raw_product(raw, category)
        pipeline = CatalogPipeline()
        for product in products:
            pipeline.process_item(product, spider)
        return products

    def test_shopify_passes_store_page_and_category_and_rejects_bad_payload(
        self,
    ) -> None:
        """Shopify wiring persists its configured store and source page."""
        spider = DarkLabSpider()
        assert (
            self._persist(spider, {"id": "bad", "handle": "", "variants": []}, "whey")
            == []
        )
        assert ScrapedItem.objects.count() == 0
        raw = {
            "id": "shopify-product-1",
            "title": "Whey Test",
            "handle": "whey-test",
            "variants": [
                {
                    "id": "shopify-variant-1",
                    "title": "Default Title",
                    "price": "10.00",
                    "available": True,
                }
            ],
        }
        items = self._persist(spider, raw, "whey-protein")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "dark_lab"
        assert item.source_page is not None
        assert (
            item.source_page.url
            == "https://www.darklabsuplementos.com.br/products/whey-test"
        )
        assert item.offer.category == "whey-protein"

    def test_vtex_passes_store_page_and_category_and_rejects_bad_payload(self) -> None:
        """VTEX wiring persists its configured store and source page."""
        spider = BlackSkullSpider()
        assert (
            self._persist(
                spider, {"productId": "bad", "linkText": "", "items": []}, "proteina"
            )
            == []
        )
        assert ScrapedItem.objects.count() == 0
        raw = {
            "productId": "vtex-product-1",
            "productName": "Whey Test",
            "linkText": "whey-test",
            "items": [
                {
                    "itemId": "vtex-item-1",
                    "sellers": [
                        {
                            "sellerDefault": True,
                            "commertialOffer": {
                                "Price": "10.00",
                                "AvailableQuantity": 2,
                            },
                        }
                    ],
                }
            ],
        }
        items = self._persist(spider, raw, "proteina")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "black_skull"
        assert item.source_page is not None
        assert item.source_page.url == "https://www.blackskullusa.com.br/whey-test/p"
        assert item.offer.category == "proteina"

    def test_nuvemshop_passes_store_page_and_category_and_rejects_bad_payload(
        self,
    ) -> None:
        """Nuvemshop wiring persists its configured store and source page."""
        spider = DuxSpider()
        assert (
            self._persist(
                spider,
                {"sku": "bad", "offers": {"url": "", "price": "N/A"}},
                "produtos",
            )
            == []
        )
        assert ScrapedItem.objects.count() == 0
        raw = {
            "@type": "Product",
            "name": "Whey Test",
            "sku": "nuvem-sku-1",
            "offers": {
                "url": "https://duxhumanhealth.com/produtos/whey-test/?ref=listing",
                "price": "10.00",
                "availability": "InStock",
            },
        }
        items = self._persist(spider, raw, "produtos")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "dux_nutrition"
        assert item.source_page is not None
        assert item.source_page.url == "https://duxhumanhealth.com/produtos/whey-test/"
        assert item.offer.category == "produtos"

    def test_wapstore_passes_store_page_and_category_and_rejects_bad_payload(
        self,
    ) -> None:
        """Wap.Store wiring persists its configured store and source page."""
        spider = GrowthSpider()
        assert (
            self._persist(
                spider,
                {"id": "bad", "nome": "Bad", "link": "", "precos": {"por": "N/A"}},
                "/proteina/",
            )
            == []
        )
        assert ScrapedItem.objects.count() == 0
        raw = {
            "id": "wap-item-1",
            "nome": "Whey Test",
            "link": "/whey-test",
            "precos": {"por": "10.00"},
        }
        items = self._persist(spider, raw, "/proteina/")
        assert len(items) == 1
        item = ScrapedItem.objects.get()
        assert item.offer.store_slug == "growth"
        assert item.source_page is not None
        assert item.source_page.url == "https://www.gsuplementos.com.br/whey-test"
        assert item.offer.category == "/proteina/"
