from decimal import Decimal
from typing import cast

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.models import (
    Brand,
    Category,
    Product,
    ProductPriceHistory,
    ProductStore,
    Store,
)

# 2. Import HtmxHttpRequest from your view
from core.views import HtmxHttpRequest, list_view


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class ListViewTests(TestCase):
    """Tests for Product List View (Standard and HTMX)."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

        # Setup data
        self.brand1 = Brand.objects.create(
            name="Brand A", display_name="Brand A Display"
        )
        self.brand2 = Brand.objects.create(
            name="Brand B", display_name="Brand B Display"
        )

        self.cat1 = Category.add_root(name="Category 1")
        self.cat2 = Category.add_root(name="Category 2")

        self.product1 = Product.objects.create(
            name="Protein A", brand=self.brand1, category=self.cat1, weight=1000
        )
        self.product2 = Product.objects.create(
            name="Protein B", brand=self.brand2, category=self.cat2, weight=900
        )

        # Need prices for stats to work properly or at least not crash
        self.store = Store.objects.create(
            name="Store 1", display_name="Store 1 Display"
        )
        self.ps1 = ProductStore.objects.create(
            product=self.product1,
            store=self.store,
            affiliate_link="http://example.com/1",
        )
        ProductPriceHistory.objects.create(
            store_product_link=self.ps1, price=Decimal("100.00")
        )

        self.ps2 = ProductStore.objects.create(
            product=self.product2,
            store=self.store,
            affiliate_link="http://example.com/2",
        )
        ProductPriceHistory.objects.create(
            store_product_link=self.ps2, price=Decimal("200.00")
        )

    def test_product_list_view_standard(self):
        """Standard GET request should render the full template."""
        request = self.factory.get(reverse("list"))
        request.htmx = False  # type: ignore

        response = list_view(cast(HtmxHttpRequest, request))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<html")
        self.assertContains(response, "Protein A")
        self.assertContains(response, "Protein B")

    def test_product_list_view_htmx(self):
        """HTMX GET request should render the partial template."""
        request = self.factory.get(reverse("list"))
        request.htmx = True  # type: ignore

        # 3. Use cast() here as well
        response = list_view(cast(HtmxHttpRequest, request))

        self.assertEqual(response.status_code, 200)
        # Should NOT contain full html structure
        self.assertNotContains(response, "<html")
        # Should contain product list elements
        self.assertContains(response, "Protein A")

    def test_product_filtering_search(self):
        """Test filtering by search query."""
        request = self.factory.get(reverse("list"), {"search": "Protein A"})
        request.htmx = False  # type: ignore

        # 3. Use cast()
        response = list_view(cast(HtmxHttpRequest, request))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Protein A")
        self.assertNotContains(response, "Protein B")

    def test_product_filtering_brand(self):
        """Test filtering by brand."""
        request = self.factory.get(reverse("list"), {"brand": "Brand B"})
        request.htmx = False  # type: ignore

        # 3. Use cast()
        response = list_view(cast(HtmxHttpRequest, request))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Protein A")
        self.assertContains(response, "Protein B")
