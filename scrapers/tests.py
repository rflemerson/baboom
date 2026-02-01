import logging
from decimal import Decimal

from django.test import TestCase

from core.models import Brand, Product, ProductPriceHistory, ProductStore, Store
from scrapers.models import ScrapedItem
from scrapers.services import ScraperService
from scrapers.spiders.blackskull import BlackSkullSpider
from scrapers.spiders.dark_lab import DarkLabSpider
from scrapers.spiders.dux import DuxSpider
from scrapers.spiders.growth import GrowthSpider
from scrapers.types import ProductIngestionInput

# Disable logging during tests
logging.getLogger("scrapers").setLevel(logging.CRITICAL)


class ScraperIntegrationTests(TestCase):
    """
    Integration tests for Spiders.

    Tests hitting REAL APIs.
    """

    def test_blackskull_spider(self):
        """Test BlackSkull spider execution."""
        spider = BlackSkullSpider(categories=["proteina"])

        items = spider.crawl()

        self.assertTrue(len(items) > 0, "BlackSkull spider should return items")
        self.assertTrue(
            ScrapedItem.objects.filter(store_slug="black_skull").count() > 0
        )

        first = ScrapedItem.objects.filter(store_slug="black_skull").first()
        self.assertIsNotNone(first)

    def test_darklab_spider(self):
        """Test DarkLab spider execution."""
        spider = DarkLabSpider(categories=["whey-protein"])

        items = spider.crawl()

        self.assertTrue(len(items) > 0, "DarkLab spider should return items")
        self.assertTrue(ScrapedItem.objects.filter(store_slug="dark_lab").count() > 0)

        first = ScrapedItem.objects.filter(store_slug="dark_lab").first()
        self.assertIsNotNone(first)

        if first and first.stock_quantity == 100:
            pass

    def test_dux_spider(self):
        """Test Dux spider execution."""
        spider = DuxSpider(categories=["proteinas"])

        items = spider.crawl()

        self.assertTrue(len(items) > 0, "Dux spider should return items")
        self.assertTrue(
            ScrapedItem.objects.filter(store_slug="dux_nutrition").count() > 0
        )

        first = ScrapedItem.objects.filter(store_slug="dux_nutrition").first()
        self.assertIsNotNone(first)

    def test_growth_spider(self):
        """Test Growth spider execution."""
        spider = GrowthSpider(categories=["/vegano/"])

        items = spider.crawl()

        self.assertTrue(len(items) > 0, "Growth spider should return items")
        self.assertTrue(ScrapedItem.objects.filter(store_slug="growth").count() > 0)

        first = ScrapedItem.objects.filter(store_slug="growth").first()
        self.assertIsNotNone(first)


class SyncPriceToCoreTests(TestCase):
    """Unit tests for ScraperService logic (save_product and sync_price_to_core)."""

    def setUp(self):
        """Set up test data."""
        self.brand = Brand.objects.create(name="test_brand", display_name="Test Brand")
        self.store = Store.objects.create(name="test_store", display_name="Test Store")
        self.product = Product.objects.create(
            name="Test Whey",
            brand=self.brand,
            weight=900,
        )
        self.product_store = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="TEST123",
            product_link="https://test.com/product",
        )

    def test_save_product_creates_price_history_for_linked_item(self):
        """Test that saving a product creates a price history record."""
        ScrapedItem.objects.create(
            store_slug="test_store",
            external_id="TEST123",
            status=ScrapedItem.Status.LINKED,
            product_store=self.product_store,
            price=Decimal("100.00"),
        )

        input_data = ProductIngestionInput(
            store_slug="test_store",
            external_id="TEST123",
            price=Decimal("199.90"),
            stock_status=ScrapedItem.StockStatus.AVAILABLE,
        )
        ScraperService.save_product(input_data)

        self.assertEqual(ProductPriceHistory.objects.count(), 1)
        price_record = ProductPriceHistory.objects.first()

        # Ensure not None for MyPy
        if price_record is None:
            self.fail("Price history record should be created but was None")

        self.assertEqual(price_record.price, Decimal("199.90"))

    def test_sync_logic_skips_if_price_unchanged(self):
        """Test that sync skips if price is unchanged."""
        ProductPriceHistory.objects.create(
            store_product_link=self.product_store,
            price=Decimal("199.90"),
            stock_status="A",
        )

        item = ScrapedItem.objects.create(
            store_slug="test_store",
            external_id="TEST123",
            price=Decimal("199.90"),
            stock_status="A",
            status=ScrapedItem.Status.LINKED,
            product_store=self.product_store,
        )

        result = ScraperService.sync_price_to_core(item)

        self.assertFalse(result)
        self.assertEqual(ProductPriceHistory.objects.count(), 1)

    def test_sync_logic_creates_new_record_on_price_change(self):
        """Test that sync creates a new record on price change."""
        item = ScrapedItem.objects.create(
            store_slug="test_store",
            external_id="TEST123",
            price=Decimal("199.90"),
            stock_status="A",
            status=ScrapedItem.Status.LINKED,
            product_store=self.product_store,
        )

        ScraperService.sync_price_to_core(item)
        self.assertEqual(ProductPriceHistory.objects.count(), 1)

        item.price = Decimal("179.90")
        item.save()

        ScraperService.sync_price_to_core(item)

        self.assertEqual(ProductPriceHistory.objects.count(), 2)

        try:
            latest = ProductPriceHistory.objects.latest("collected_at")
        except ProductPriceHistory.DoesNotExist:
            self.fail("Latest history not found")

        self.assertEqual(latest.price, Decimal("179.90"))
