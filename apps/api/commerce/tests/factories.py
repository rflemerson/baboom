"""Factories for commercial identities."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from commerce.models import Channel, Currency, Market, SellerAccount


def brl() -> Currency:
    """Return the seeded real."""
    return Currency.objects.get(code="BRL")


class ChannelFactory(DjangoModelFactory):
    """An independent store channel."""

    class Meta:
        """Factory configuration."""

        model = Channel

    kind = Channel.Kind.INDEPENDENT_STORE
    name = factory.Sequence(lambda number: f"Channel {number}")
    adapter = "shopify"


class MarketFactory(DjangoModelFactory):
    """A Brazilian market of a fresh channel."""

    class Meta:
        """Factory configuration."""

        model = Market

    channel = factory.SubFactory(ChannelFactory)
    country = "BR"
    currency = factory.LazyFunction(brl)
    timezone = "America/Sao_Paulo"
    namespace = factory.Sequence(lambda number: f"market-{number}")


class SellerAccountFactory(DjangoModelFactory):
    """A third-party seller of a market."""

    class Meta:
        """Factory configuration."""

        model = SellerAccount

    market = factory.SubFactory(MarketFactory)
    external_id = factory.Sequence(lambda number: f"seller-{number}")
    name_raw = factory.Sequence(lambda number: f"Seller {number}")
