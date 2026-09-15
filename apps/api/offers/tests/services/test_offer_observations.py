"""Tests for the offer observation application service."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from offers.models import Offer, PriceObservation, StockStatus
from offers.services import OfferObservationService
from offers.tests.factories import OfferFactory

INITIAL_PRICE = Decimal("99.90")
UPDATED_PRICE = Decimal("89.90")
EXPECTED_OBSERVATION_COUNT = 2


class OfferObservationServiceTests(TestCase):
    """The service owns offer upserts and append-only price history."""

    def setUp(self) -> None:
        """Create the service under test."""
        self.service = OfferObservationService()

    def test_first_record_creates_offer_and_observation(self) -> None:
        """A new priced listing creates an offer and its first observation."""
        result = self.service.record(
            store_slug="test-store",
            external_id="sku-1",
            price=INITIAL_PRICE,
            stock_status="unknown",
            snapshot={"name": "Whey", "url": "https://example.com/whey"},
        )

        offer = Offer.objects.get()
        observation = PriceObservation.objects.get()
        assert result.offer == offer
        assert result.created is True
        assert result.changed is True
        assert offer.current_stock_status == StockStatus.AVAILABLE
        assert offer.url == "https://example.com/whey"
        assert observation.price == INITIAL_PRICE
        assert observation.stock_status == StockStatus.AVAILABLE

    def test_unchanged_record_updates_snapshot_without_new_observation(self) -> None:
        """Repeating the same price and stock does not grow price history."""
        self.service.record(
            store_slug="test-store",
            external_id="sku-1",
            price=INITIAL_PRICE,
            stock_status=StockStatus.AVAILABLE,
            snapshot={"name": "Old name"},
        )

        result = self.service.record(
            store_slug="test-store",
            external_id="sku-1",
            price=INITIAL_PRICE,
            stock_status=StockStatus.AVAILABLE,
            snapshot={"name": "Current name"},
        )

        assert result.created is False
        assert result.changed is False
        assert PriceObservation.objects.count() == 1
        assert Offer.objects.get().name == "Current name"

    def test_price_or_stock_change_appends_observation(self) -> None:
        """A price or stock movement creates a second historical snapshot."""
        self.service.record(
            store_slug="test-store",
            external_id="sku-1",
            price=INITIAL_PRICE,
            stock_status=StockStatus.AVAILABLE,
            snapshot={},
        )

        result = self.service.record(
            store_slug="test-store",
            external_id="sku-1",
            price=UPDATED_PRICE,
            stock_status=StockStatus.OUT_OF_STOCK,
            snapshot={},
        )

        assert result.created is False
        assert result.changed is True
        assert PriceObservation.objects.count() == EXPECTED_OBSERVATION_COUNT
        latest = PriceObservation.objects.latest()
        assert latest.price == UPDATED_PRICE
        assert latest.stock_status == StockStatus.OUT_OF_STOCK

    def test_missing_price_updates_offer_without_observation(self) -> None:
        """A price-less listing refreshes current state but records no history."""
        offer = OfferFactory(store_slug="test-store", external_id="sku-1")

        result = self.service.record(
            store_slug=offer.store_slug,
            external_id=offer.external_id,
            price=None,
            stock_status=StockStatus.OUT_OF_STOCK,
            snapshot={"name": "Unavailable"},
        )

        assert result.created is False
        assert result.changed is False
        assert PriceObservation.objects.count() == 0
        offer.refresh_from_db()
        assert offer.current_price is None
        assert offer.current_stock_status == StockStatus.OUT_OF_STOCK

    def test_resolve_for_listing_converts_price_and_empty_identity(self) -> None:
        """A listing DTO maps its URL and price into the common record operation."""
        listing = SimpleNamespace(
            external_id=None,
            product_link="https://example.com/whey",
            price=INITIAL_PRICE,
            stock_status=StockStatus.AVAILABLE,
        )

        offer = self.service.resolve_for_listing(
            store_slug="test-store",
            listing=listing,
        )

        assert offer.external_id == ""
        assert offer.url == listing.product_link
        assert offer.current_price == INITIAL_PRICE
        assert PriceObservation.objects.get().price == INITIAL_PRICE
