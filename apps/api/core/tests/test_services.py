"""Tests for core application services."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.dtos import StoreListingPayload
from core.models import Brand, Product, ProductPriceHistory, ProductStore, Store
from core.services import ProductStoreService


class ProductStoreServiceTests(TestCase):
    """Coverage for store listing synchronization rules."""

    UPDATED_HISTORY_COUNT = 2
    UPDATED_PRICE = Decimal("109.90")

    def setUp(self) -> None:
        """Create a product and two stores for listing sync tests."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Whey Concentrado",
            brand=self.brand,
            weight=900,
            packaging=Product.Packaging.CONTAINER,
        )
        self.store = Store.objects.create(name="growth", display_name="Growth")
        self.other_store = Store.objects.create(name="dux", display_name="Dux")
        self.service = ProductStoreService()

    def test_replace_listings_updates_existing_listing_without_recreating_it(
        self,
    ) -> None:
        """Existing listings should keep identity while mutable fields are updated."""
        original_listing = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/old",
            affiliate_link="https://aff.example/old",
        )
        ProductPriceHistory.objects.create(
            store_product_link=original_listing,
            price="99.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="sku-2",
                    product_link="https://growth.example/new",
                    affiliate_link="https://aff.example/new",
                    price=99.90,
                    stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
                ),
            ],
        )

        updated_listing = ProductStore.objects.get(
            product=self.product,
            store=self.store,
        )
        assert updated_listing.pk == original_listing.pk
        assert updated_listing.external_id == "sku-2"
        assert updated_listing.product_link == "https://growth.example/new"
        assert updated_listing.affiliate_link == "https://aff.example/new"
        assert updated_listing.price_history.count() == 1

    def test_replace_listings_adds_history_only_when_price_or_stock_changes(
        self,
    ) -> None:
        """A new price history row should be appended only for meaningful changes."""
        listing = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/item",
        )
        ProductPriceHistory.objects.create(
            store_product_link=listing,
            price="99.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="sku-1",
                    product_link="https://growth.example/item",
                    price=109.90,
                    stock_status=ProductPriceHistory.StockStatus.LAST_UNITS,
                ),
            ],
        )

        listing.refresh_from_db()
        latest_history = listing.price_history.first()
        assert listing.price_history.count() == self.UPDATED_HISTORY_COUNT
        assert latest_history is not None
        assert latest_history.price == self.UPDATED_PRICE
        assert latest_history.stock_status == ProductPriceHistory.StockStatus.LAST_UNITS

    def test_replace_listings_deletes_removed_store_links(self) -> None:
        """Listings omitted from the desired state should be removed."""
        retained_listing = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            external_id="growth-1",
            product_link="https://growth.example/item",
        )
        removed_listing = ProductStore.objects.create(
            product=self.product,
            store=self.other_store,
            external_id="dux-1",
            product_link="https://dux.example/item",
        )
        ProductPriceHistory.objects.create(
            store_product_link=retained_listing,
            price="99.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )
        ProductPriceHistory.objects.create(
            store_product_link=removed_listing,
            price="89.90",
            stock_status=ProductPriceHistory.StockStatus.AVAILABLE,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_name="Growth",
                    external_id="growth-1",
                    product_link="https://growth.example/item",
                    price=99.90,
                ),
            ],
        )

        assert ProductStore.objects.filter(pk=retained_listing.pk).exists()
        assert not ProductStore.objects.filter(pk=removed_listing.pk).exists()

    def test_replace_listings_rejects_duplicate_store_rows(self) -> None:
        """The same store should not be accepted twice for one product."""
        raised_validation_error = False

        try:
            self.service.replace_listings(
                self.product,
                [
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-1",
                        product_link="https://growth.example/1",
                        price=99.90,
                    ),
                    StoreListingPayload(
                        store_name="Growth",
                        external_id="growth-2",
                        product_link="https://growth.example/2",
                        price=109.90,
                    ),
                ],
            )
        except ValidationError:
            raised_validation_error = True

        assert raised_validation_error
