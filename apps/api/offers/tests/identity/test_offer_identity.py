"""An offer is one seller's proposal for one variant of one listing."""

from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from commerce.tests.factories import MarketFactory, SellerAccountFactory
from common.testing import raised
from offers.models import Listing, ListingVariant, OfferSourceIdentity
from offers.services import (
    ListingRef,
    OfferIdentityRef,
    OfferIdentityService,
    VariantRef,
)
from offers.tests.factories import OfferFactory

LISTING = ListingRef(external_id="MLB1", url="https://example.com/p", title="Whey")
VARIANT = VariantRef(
    external_id="v1",
    options=({"name": "Sabor", "value": "Chocolate"},),
)


class OfferIdentityTests(TestCase):
    """Sellers, markets and keys never collide or move silently."""

    def test_two_sellers_of_one_variant_are_two_offers(self) -> None:
        """Neither seller's price or stock overwrites the other's."""
        market = MarketFactory()
        first_seller = SellerAccountFactory(market=market)
        second_seller = SellerAccountFactory(market=market)
        first, second = OfferFactory(), OfferFactory()
        service = OfferIdentityService()

        service.bind(
            first,
            OfferIdentityRef(
                market=market,
                listing=LISTING,
                variant=VARIANT,
                seller_account=first_seller,
                scheme="marketplace",
                key=f"v1@{first_seller.external_id}",
            ),
        )
        service.bind(
            second,
            OfferIdentityRef(
                market=market,
                listing=LISTING,
                variant=VARIANT,
                seller_account=second_seller,
                scheme="marketplace",
                key=f"v1@{second_seller.external_id}",
            ),
        )

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.listing_variant_id == second.listing_variant_id
        assert first.seller_account == first_seller
        assert second.seller_account == second_seller
        assert ListingVariant.objects.count() == 1

    def test_same_external_id_in_two_markets_is_two_listings(self) -> None:
        """MLB1 in Brazil and MLB1 elsewhere name different pages."""
        service = OfferIdentityService()
        brazil = service.listing(MarketFactory(), LISTING)
        other = service.listing(MarketFactory(country="MX"), LISTING)

        assert brazil.pk != other.pk
        assert set(Listing.objects.values_list("pk", flat=True)) == {
            brazil.pk,
            other.pk,
        }

    def test_a_known_seller_is_never_overwritten(self) -> None:
        """A different seller is a different offer, not an update."""
        market = MarketFactory()
        original = SellerAccountFactory(market=market)
        offer = OfferFactory()
        service = OfferIdentityService()
        service.bind(
            offer,
            OfferIdentityRef(
                market=market,
                listing=LISTING,
                variant=VARIANT,
                seller_account=original,
                scheme="marketplace",
                key="v1@a",
            ),
        )

        with self.assertLogs("offers.services", "WARNING"):
            service.bind(
                offer,
                OfferIdentityRef(
                    market=market,
                    listing=LISTING,
                    variant=VARIANT,
                    seller_account=SellerAccountFactory(market=market),
                    scheme="marketplace",
                    key="v1@a",
                ),
            )

        offer.refresh_from_db()
        assert offer.seller_account == original

    def test_a_key_never_moves_to_another_offer(self) -> None:
        """The second offer claiming a key is logged, not given it."""
        market = MarketFactory()
        first, second = OfferFactory(), OfferFactory()
        service = OfferIdentityService()
        for offer in (first, second):
            with self.assertNoLogs("offers.services", "ERROR"):
                service.bind(
                    offer,
                    OfferIdentityRef(
                        market=market,
                        listing=LISTING,
                        variant=VARIANT,
                        seller_account=None,
                        scheme="marketplace",
                        key="v1@unknown",
                    ),
                )

        identity = OfferSourceIdentity.objects.get(scheme="marketplace")
        assert identity.offer == first

    def test_the_legacy_alias_is_recorded(self) -> None:
        """Store slug and external id stay findable as a source identity."""
        offer = OfferFactory(external_id="sku-9")
        market = MarketFactory()
        OfferIdentityService().bind(
            offer,
            OfferIdentityRef(
                market=market,
                listing=LISTING,
                variant=VARIANT,
                seller_account=None,
                scheme="shopify",
                key="v1@owner",
            ),
        )

        assert OfferSourceIdentity.objects.filter(
            offer=offer,
            namespace=market.namespace,
            scheme="legacy",
            key="sku-9",
        ).exists()

    def test_a_listing_id_is_unique_per_market(self) -> None:
        """The database refuses a duplicate even outside the service."""
        market = MarketFactory()
        Listing.objects.create(market=market, external_id="X")
        raised(
            lambda: Listing.objects.create(market=market, external_id="X"),
            IntegrityError,
        )
