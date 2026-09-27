"""Factories for core catalog models used by backend tests."""

from __future__ import annotations

from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from core.models import Brand, NutritionFacts, Product, ProductNutrition, Store


class BrandFactory(DjangoModelFactory):
    """Create a brand with unique catalog-facing names."""

    class Meta:
        """Factory configuration."""

        model = Brand

    name = factory.Sequence(lambda number: f"brand-{number}")
    display_name = factory.Sequence(lambda number: f"Brand {number}")


class StoreFactory(DjangoModelFactory):
    """Create a store with unique catalog-facing names."""

    class Meta:
        """Factory configuration."""

        model = Store

    name = factory.Sequence(lambda number: f"store-{number}")
    display_name = factory.Sequence(lambda number: f"Store {number}")


class ProductFactory(DjangoModelFactory):
    """Create a valid simple product in canonical mass units."""

    class Meta:
        """Factory configuration."""

        model = Product

    name = factory.Sequence(lambda number: f"Product {number}")
    brand = factory.SubFactory(BrandFactory)
    net_mass = Decimal(900)
    ean = factory.Sequence(lambda number: f"789000000{number:05d}")


class NutritionFactsFactory(DjangoModelFactory):
    """Create a nutrition label with canonical mass values."""

    class Meta:
        """Factory configuration."""

        model = NutritionFacts

    description = factory.Sequence(lambda number: f"Label {number}")
    serving_size = Decimal(30)
    proteins = Decimal(24)


class ProductNutritionFactory(DjangoModelFactory):
    """Create a product linked to one nutrition profile."""

    class Meta:
        """Factory configuration."""

        model = ProductNutrition

    product = factory.SubFactory(ProductFactory)
    nutrition_facts = factory.SubFactory(NutritionFactsFactory)
