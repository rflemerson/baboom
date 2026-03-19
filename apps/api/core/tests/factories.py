"""Factory helpers for core app tests."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from core.models import (
    Brand,
    NutritionFacts,
    Product,
    ProductStore,
    Store,
)


class BrandFactory(DjangoModelFactory):
    """Factory for Brand model."""

    class Meta:
        """Meta class."""

        model = Brand

    name = factory.Sequence(lambda n: f"brand-{n}")
    display_name = factory.Sequence(lambda n: f"Brand {n}")
    description = factory.Faker("paragraph")


class StoreFactory(DjangoModelFactory):
    """Factory for Store model."""

    class Meta:
        """Meta class."""

        model = Store

    name = factory.Sequence(lambda n: f"store-{n}")
    display_name = factory.Sequence(lambda n: f"Store {n}")
    description = factory.Faker("paragraph")


class ProductFactory(DjangoModelFactory):
    """Factory for Product model."""

    class Meta:
        """Meta class."""

        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    brand = factory.SubFactory(BrandFactory)
    description = factory.Faker("paragraph")
    weight = factory.Faker("random_int", min=100, max=2000)
    packaging = Product.Packaging.CONTAINER


class ProductStoreFactory(DjangoModelFactory):
    """Factory for ProductStore model."""

    class Meta:
        """Meta class."""

        model = ProductStore

    product = factory.SubFactory(ProductFactory)
    store = factory.SubFactory(StoreFactory)
    product_link = factory.Faker("url")


class NutritionFactsFactory(DjangoModelFactory):
    """Factory for NutritionFacts model."""

    class Meta:
        """Meta class."""

        model = NutritionFacts

    serving_size_grams = factory.Faker("random_int", min=20, max=50)
    proteins = factory.Faker("pydecimal", left_digits=2, right_digits=1, positive=True)
    carbohydrates = factory.Faker(
        "pydecimal",
        left_digits=2,
        right_digits=1,
        positive=True,
    )
    total_fats = factory.Faker(
        "pydecimal",
        left_digits=1,
        right_digits=1,
        positive=True,
    )
    energy_kcal = factory.Faker("random_int", min=80, max=200)
    description = factory.Faker("sentence")
