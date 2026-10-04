"""Ingestion places each offer under its market, listing, variant and seller."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.test import TestCase

from commerce.models import Market, SellerAccount
from offers.models import Offer
from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.models import ScrapedPage
from scrapers.stores.blackskull import BlackSkullSpider
from scrapers.stores.dark_lab import DarkLabSpider

if TYPE_CHECKING:
    from scrapers.crawler.base import CatalogSpider

VTEX_PRODUCT = {
    "productId": "77",
    "productName": "Whey",
    "linkText": "whey",
    "items": [
        {
            "itemId": "770",
            "sellers": [
                {
                    "sellerId": "1",
                    "sellerName": "Black Skull",
                    "sellerDefault": True,
                    "commertialOffer": {"Price": 99.9, "AvailableQuantity": 3},
                },
            ],
        },
        {
            "itemId": "771",
            "sellers": [
                {
                    "sellerId": "acme",
                    "sellerName": "Acme",
                    "sellerDefault": True,
                    "commertialOffer": {"Price": 89.9, "AvailableQuantity": 3},
                },
            ],
        },
    ],
}

SHOPIFY_PRODUCT = {
    "id": 5,
    "handle": "whey",
    "title": "Whey",
    "options": [{"name": "Sabor"}],
    "variants": [
        {"id": 50, "price": 14990, "available": True, "option1": "Chocolate"},
    ],
}


def _ingest(spider: CatalogSpider, raw: dict) -> None:
    for product in spider.process_raw_product(raw, "whey"):
        CatalogPipeline().process_item(product, spider)


class IngestionIdentityTests(TestCase):
    """The spider's declared market and the payload's seller reach the offer."""

    def test_shopify_offer_is_sold_by_the_store_itself(self) -> None:
        """A platform without third-party sellers names the channel owner."""
        _ingest(DarkLabSpider(), SHOPIFY_PRODUCT)

        market = Market.objects.get(namespace="dark_lab")
        assert market.country == "BR"
        assert market.currency_id == "BRL"
        assert market.provenance == "source_contract"
        owner = SellerAccount.objects.get(market=market)
        assert owner.is_channel_owner
        offer = owner.offers.get()
        assert offer.listing_variant.listing.external_id == "5"
        assert offer.listing_variant.options == [
            {"name": "Sabor", "value": "Chocolate"},
        ]

    def test_vtex_seller_one_is_the_store_and_others_are_sellers(self) -> None:
        """Only seller "1" is the store; any other id is its own account."""
        _ingest(BlackSkullSpider(), VTEX_PRODUCT)

        accounts = {
            account.external_id: account
            for account in SellerAccount.objects.filter(market__namespace="black_skull")
        }
        assert accounts["1"].is_channel_owner
        assert not accounts["acme"].is_channel_owner
        assert accounts["acme"].name_raw == "Acme"
        assert accounts["acme"].offers.get().external_id == "771@acme"

    def test_the_source_page_points_at_its_listing(self) -> None:
        """Crawl evidence stays, attached to the listing it describes."""
        _ingest(DarkLabSpider(), SHOPIFY_PRODUCT)

        page = ScrapedPage.objects.get()
        assert page.listing is not None
        assert page.listing.external_id == "5"

    def test_recrawling_creates_no_duplicates(self) -> None:
        """Identity is idempotent across runs."""
        _ingest(DarkLabSpider(), SHOPIFY_PRODUCT)
        _ingest(DarkLabSpider(), SHOPIFY_PRODUCT)

        assert Market.objects.count() == 1
        assert SellerAccount.objects.count() == 1


class SellerCollisionTests(TestCase):
    """R03: a key owned by another seller never receives this seller's facts."""

    def test_a_collision_keeps_both_sellers_and_their_prices(self) -> None:
        """The legacy third-party offer keeps its price; seller 1 gets its own."""
        _ingest(BlackSkullSpider(), VTEX_PRODUCT)
        legacy = Offer.objects.get(external_id="770")
        third = SellerAccount.objects.get(external_id="acme")
        Offer.objects.filter(pk=legacy.pk).update(
            seller_account=third,
            current_price=Decimal("250.00"),
        )

        with self.assertLogs("scrapers.services", "WARNING"):
            _ingest(BlackSkullSpider(), VTEX_PRODUCT)

        legacy.refresh_from_db()
        moved = Offer.objects.get(external_id="770@owner")
        assert legacy.current_price == Decimal("250.00")
        assert legacy.seller_account == third
        assert legacy.delisted_at is None
        assert moved.current_price == Decimal("99.90")
        assert moved.seller_account.is_channel_owner
        assert moved.price_points.filter(source_field="commertialOffer.Price").exists()
        assert (
            not legacy.price_points.filter(amount=Decimal("99.9"))
            .exclude(
                observed_at__lt=moved.created_at,
            )
            .exists()
        )
