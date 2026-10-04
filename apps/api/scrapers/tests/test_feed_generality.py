"""SYNTHETIC: a fictitious marketplace onboarded by configuration through a feed.

Nothing here describes a real Amazon, Mercado Livre or store campaign. These
scenarios prove the model admits channels, sellers and markets the eight
crawled stores never exercise, without changing the engine.
"""

from __future__ import annotations

import copy
from decimal import Decimal

from django.test import TestCase

from commerce.models import Currency, Market, SellerAccount
from offers.models import FeaturedOfferObservation, Offer, OfferPriceObservation
from scrapers.crawler.pipelines import CatalogPipeline
from scrapers.crawler.spiders.feed import FeedSpider


class SyntheticMarketplaceMX(FeedSpider):
    """A fictitious marketplace in Mexico, configured, not coded."""

    name = "synthetic_marketplace_mx"
    BRAND_NAME = "Synthetic Marketplace"
    STORE_SLUG = "synthetic_marketplace_mx"
    CHANNEL_KIND = "marketplace"
    MARKET_COUNTRY = "MX"
    MARKET_CURRENCY = "MXN"
    MARKET_TIMEZONE = "America/Mexico_City"
    FEED_URL = "https://feed.example/mx"


class SyntheticMarketplaceBR(SyntheticMarketplaceMX):
    """The same fictitious marketplace in Brazil: another market."""

    name = "synthetic_marketplace_br"
    STORE_SLUG = "synthetic_marketplace_br"
    MARKET_COUNTRY = "BR"
    MARKET_CURRENCY = "BRL"
    MARKET_TIMEZONE = "America/Sao_Paulo"


LISTING = {
    "id": "MX100",
    "url": "https://feed.example/MX100",
    "title": "Whey 1 kg",
    "complete": True,
    "variants": [
        {
            "id": "v1",
            "options": [{"name": "Sabor", "value": "Vainilla"}],
            "offers": [
                {
                    "id": "o1",
                    "seller": {"id": "123", "name": "Tienda A"},
                    "featured": True,
                    "stock": "available",
                    "prices": [
                        {"role": "payable", "amount": "899.00"},
                        {
                            "role": "payable",
                            "amount": "850.00",
                            "payment_scope": "method",
                            "payment_label_raw": "OXXO Pay",
                        },
                    ],
                },
                {
                    "id": "o2",
                    "seller": {"id": "456", "name": "Tienda B"},
                    "stock": "available",
                    "prices": [{"role": "payable", "amount": "879.00"}],
                },
            ],
        },
    ],
}


def _ingest(spider_class: type[FeedSpider], listing: dict) -> None:
    spider = spider_class()
    for product in spider.process_raw_product(listing, "feed"):
        CatalogPipeline().process_item(product, spider)


class FeedOnboardingTests(TestCase):
    """A new channel, market and currency, with no engine change."""

    def test_two_sellers_of_one_listing_are_two_offers(self) -> None:
        """Neither seller's price overwrites the other's."""
        _ingest(SyntheticMarketplaceMX, LISTING)

        prices = dict(Offer.objects.values_list("external_id", "current_price"))
        assert prices == {"v1@123": Decimal("899.00"), "v1@456": Decimal("879.00")}
        market = Market.objects.get(namespace="synthetic_marketplace_mx")
        assert market.currency_id == "MXN"
        assert market.channel.kind == "marketplace"

    def test_the_same_ids_in_two_markets_are_distinct(self) -> None:
        """Listing MX100 and seller 123 in Brazil are other rows."""
        _ingest(SyntheticMarketplaceMX, LISTING)
        _ingest(SyntheticMarketplaceBR, LISTING)

        assert Offer.objects.filter(external_id="v1@123").count() == len(
            ["mx", "br"],
        )
        markets = {"synthetic_marketplace_mx", "synthetic_marketplace_br"}
        sellers = SellerAccount.objects.filter(external_id="123")
        assert set(sellers.values_list("market__namespace", flat=True)) == markets

    def test_an_unknown_payment_label_is_kept_without_a_method(self) -> None:
        """OXXO Pay is not Pix, not card, not any."""
        _ingest(SyntheticMarketplaceMX, LISTING)

        oxxo = OfferPriceObservation.objects.get(payment_label_raw="OXXO Pay")
        assert oxxo.payment_method is None
        assert oxxo.currency_id == "MXN"

    def test_a_new_featured_seller_is_an_observation(self) -> None:
        """The buy box moved to seller B; both offers remain."""
        _ingest(SyntheticMarketplaceMX, LISTING)
        moved = copy.deepcopy(LISTING)
        offers = moved["variants"][0]["offers"]
        offers[0]["featured"], offers[1]["featured"] = False, True

        _ingest(SyntheticMarketplaceMX, moved)

        featured = FeaturedOfferObservation.objects.order_by("observed_at", "pk")
        assert [f.offer.external_id for f in featured] == ["v1@123", "v1@456"]
        assert Offer.objects.filter(delisted_at__isnull=True).count() == len(offers)

    def test_a_partial_feed_never_delists_absent_sellers(self) -> None:
        """A top-N listing of sellers proves nothing about the others."""
        _ingest(SyntheticMarketplaceMX, LISTING)
        partial = copy.deepcopy(LISTING)
        partial["complete"] = False
        partial["variants"][0]["offers"] = partial["variants"][0]["offers"][:1]

        _ingest(SyntheticMarketplaceMX, partial)

        assert Offer.objects.get(external_id="v1@456").delisted_at is None

    def test_a_complete_feed_delists_a_seller_that_left(self) -> None:
        """A complete listing of sellers is evidence of absence."""
        _ingest(SyntheticMarketplaceMX, LISTING)
        complete = copy.deepcopy(LISTING)
        complete["variants"][0]["offers"] = complete["variants"][0]["offers"][:1]

        _ingest(SyntheticMarketplaceMX, complete)

        assert Offer.objects.get(external_id="v1@456").delisted_at is not None

    def test_an_offer_without_a_seller_is_not_invented(self) -> None:
        """A price naming no seller does not become anyone's offer."""
        anonymous = copy.deepcopy(LISTING)
        anonymous["variants"][0]["offers"][1]["seller"] = {}

        _ingest(SyntheticMarketplaceMX, anonymous)

        assert list(Offer.objects.values_list("external_id", flat=True)) == ["v1@123"]


class CurrencyPrecisionTests(TestCase):
    """Precision is the currency's, never two places by assumption."""

    def test_currencies_carry_their_own_precision(self) -> None:
        """Chilean pesos have no cents; reais have two."""
        assert Currency.objects.get(code="CLP").minor_unit == 0
        assert Currency.objects.get(code="BRL").minor_unit == len("00")
