"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.forms.models import inlineformset_factory
from django.test import TestCase

from core.dtos import (
    StoreListingPayload,
)
from core.forms import ProductStoreInlineForm, ProductStoreInlineFormSet
from core.models import (
    Brand,
    Product,
    ProductStore,
    Store,
)
from core.services import (
    ProductStoreService,
)
from core.tests.helpers import (
    _link_offer,
)
from offers.models import Offer, StockStatus


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
            net_mass=Decimal(900),
            packaging=Product.Packaging.CONTAINER,
        )
        self.store = Store.objects.create(
            name="growth",
            display_name="Growth",
            scraper_slug="growth",
        )
        self.other_store = Store.objects.create(
            name="dux",
            display_name="Dux",
            scraper_slug="dux",
        )
        self.service = ProductStoreService()

    def test_replace_listings_updates_existing_listing_without_recreating_it(
        self,
    ) -> None:
        """Existing listings should keep identity while mutable fields are updated."""
        original_listing = _link_offer(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/old",
            price=99.90,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_id=self.store.id,
                    external_id="sku-2",
                    product_link="https://growth.example/new",
                    affiliate_link="https://aff.example/new",
                    price=99.90,
                    stock_status=StockStatus.AVAILABLE,
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
        assert updated_listing.offer.price_observations.count() == 1

    def test_store_inline_requires_external_id_for_listing_rows(self) -> None:
        """Manual listings need a stable merchant id before creating an offer."""
        formset_class = inlineformset_factory(
            Product,
            ProductStore,
            form=ProductStoreInlineForm,
            formset=ProductStoreInlineFormSet,
            fields=(
                "store",
                "external_id",
                "product_link",
                "affiliate_link",
                "price",
                "stock_status",
            ),
            extra=1,
            can_delete=True,
        )
        formset = formset_class(
            data={
                "store_links-TOTAL_FORMS": "1",
                "store_links-INITIAL_FORMS": "0",
                "store_links-MIN_NUM_FORMS": "0",
                "store_links-MAX_NUM_FORMS": "1000",
                "store_links-0-store": str(self.store.id),
                "store_links-0-external_id": "",
                "store_links-0-product_link": "https://growth.example/item",
                "store_links-0-affiliate_link": "",
                "store_links-0-price": "99.90",
                "store_links-0-stock_status": StockStatus.AVAILABLE,
            },
            instance=self.product,
            prefix="store_links",
        )

        assert not formset.is_valid()
        assert "store product ID" in str(formset.non_form_errors())

    def test_replace_listings_adds_history_only_when_price_or_stock_changes(
        self,
    ) -> None:
        """A new price observation should be appended only for meaningful changes."""
        listing = _link_offer(
            product=self.product,
            store=self.store,
            external_id="sku-1",
            product_link="https://growth.example/item",
            price=99.90,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_id=self.store.id,
                    external_id="sku-1",
                    product_link="https://growth.example/item",
                    price=109.90,
                    stock_status=StockStatus.LAST_UNITS,
                ),
            ],
        )

        listing.refresh_from_db()
        observations = listing.offer.price_observations
        latest_history = observations.first()
        assert observations.count() == self.UPDATED_HISTORY_COUNT
        assert latest_history is not None
        assert latest_history.price == self.UPDATED_PRICE
        assert latest_history.stock_status == StockStatus.LAST_UNITS

    def test_replace_listings_deletes_removed_store_links(self) -> None:
        """Listings omitted from the desired state should be removed."""
        retained_listing = _link_offer(
            product=self.product,
            store=self.store,
            external_id="growth-1",
            product_link="https://growth.example/item",
            price=99.90,
        )
        removed_listing = _link_offer(
            product=self.product,
            store=self.other_store,
            external_id="dux-1",
            product_link="https://dux.example/item",
            price=89.90,
        )

        self.service.replace_listings(
            self.product,
            [
                StoreListingPayload(
                    store_id=self.store.id,
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
                        store_id=self.store.id,
                        external_id="growth-1",
                        product_link="https://growth.example/1",
                        price=99.90,
                    ),
                    StoreListingPayload(
                        store_id=self.store.id,
                        external_id="growth-2",
                        product_link="https://growth.example/2",
                        price=109.90,
                    ),
                ],
            )
        except ValidationError:
            raised_validation_error = True

        assert raised_validation_error


class StoreIdentityTests(TestCase):
    """A listing reuses the offer the scraper captured for that store.

    The scraper records ``Offer.store_slug`` (``black_skull``); the store's
    ``name`` is for people (``Black Skull``). Resolving by name misses the
    captured offer and forges a second one with an artificial price history.
    """

    def test_listing_reuses_the_captured_offer_of_a_store_named_for_people(
        self,
    ) -> None:
        """Linking must not create an offer when the store already has it."""
        brand = Brand.objects.create(name="black-skull", display_name="Black Skull")
        product = Product.objects.create(
            name="Whey 3W",
            brand=brand,
            net_mass=Decimal(900),
        )
        store = Store.objects.create(
            name="Black Skull",
            display_name="Black Skull USA",
            scraper_slug="black_skull",
        )
        captured = Offer.objects.create(
            store_slug="black_skull",
            external_id="1014",
            name="Whey 3W Chocolate",
            url="https://blackskull.example/whey?skuId=1014",
            current_price=Decimal("119.90"),
        )

        ProductStoreService().replace_listings(
            product,
            [
                StoreListingPayload(
                    store_id=store.id,
                    external_id="1014",
                    product_link=captured.url,
                    price=119.90,
                ),
            ],
        )

        assert Offer.objects.count() == 1
        assert ProductStore.objects.get(product=product).offer_id == captured.pk
