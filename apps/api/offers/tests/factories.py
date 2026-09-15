"""Factories for offer models used by backend tests."""

from __future__ import annotations

from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from offers.models import Offer, PriceObservation, StockStatus


class OfferFactory(DjangoModelFactory):
    """Create an offer with a unique store identity."""

    class Meta:
        """Factory configuration."""

        model = Offer

    store_slug = factory.Sequence(lambda number: f"store-{number}")
    external_id = factory.Sequence(lambda number: f"offer-{number}")
    name = factory.Sequence(lambda number: f"Offer {number}")
    current_price = Decimal("99.90")
    current_stock_status = StockStatus.AVAILABLE


class PriceObservationFactory(DjangoModelFactory):
    """Create a price observation for a generated offer."""

    class Meta:
        """Factory configuration."""

        model = PriceObservation

    offer = factory.SubFactory(OfferFactory)
    price = Decimal("99.90")
    stock_status = StockStatus.AVAILABLE
