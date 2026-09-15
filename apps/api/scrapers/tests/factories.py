"""Factories for persisted scraper payload models."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from offers.tests.factories import OfferFactory
from scrapers.models import ScrapedItem, ScrapedPage


class ScrapedPageFactory(DjangoModelFactory):
    """Create a uniquely addressable scraped page."""

    class Meta:
        """Factory configuration."""

        model = ScrapedPage

    store_slug = factory.Sequence(lambda number: f"store-{number}")
    url = factory.Sequence(
        lambda number: f"https://store-{number}.example/products/{number}",
    )
    api_context = factory.LazyFunction(dict)


class ScrapedItemFactory(DjangoModelFactory):
    """Create a scraped item linked to an offer and source page."""

    class Meta:
        """Factory configuration."""

        model = ScrapedItem

    offer = factory.SubFactory(OfferFactory)
    source_page = factory.SubFactory(ScrapedPageFactory)
    variant_context = factory.LazyFunction(dict)
