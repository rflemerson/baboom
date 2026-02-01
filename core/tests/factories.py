import factory
from factory.django import DjangoModelFactory

from core.models import (
    AlertSubscriber,
    Brand,
    Category,
    Flavor,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
    Tag,
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


class FlavorFactory(DjangoModelFactory):
    """Factory for Flavor model."""

    class Meta:
        """Meta class."""

        model = Flavor

    name = factory.Sequence(lambda n: f"flavor-{n}")
    description = factory.Faker("sentence")


class TagFactory(DjangoModelFactory):
    """Factory for Tag model."""

    class Meta:
        """Meta class."""

        model = Tag

    name = factory.Sequence(lambda n: f"tag-{n}")
    description = factory.Faker("sentence")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to use treebeard's add_root method."""
        return model_class.add_root(**kwargs)


class CategoryFactory(DjangoModelFactory):
    """Factory for Category model."""

    class Meta:
        """Meta class."""

        model = Category

    name = factory.Sequence(lambda n: f"category-{n}")
    description = factory.Faker("sentence")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to use treebeard's add_root method."""
        return model_class.add_root(**kwargs)


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


class ProductPriceHistoryFactory(DjangoModelFactory):
    """Factory for ProductPriceHistory model."""

    class Meta:
        """Meta class."""

        model = ProductPriceHistory

    store_product_link = factory.SubFactory(ProductStoreFactory)
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)


class NutritionFactsFactory(DjangoModelFactory):
    """Factory for NutritionFacts model."""

    class Meta:
        """Meta class."""

        model = NutritionFacts

    serving_size_grams = factory.Faker("random_int", min=20, max=50)
    proteins = factory.Faker("pydecimal", left_digits=2, right_digits=1, positive=True)
    carbohydrates = factory.Faker(
        "pydecimal", left_digits=2, right_digits=1, positive=True
    )
    total_fats = factory.Faker(
        "pydecimal", left_digits=1, right_digits=1, positive=True
    )
    energy_kcal = factory.Faker("random_int", min=80, max=200)
    description = factory.Faker("sentence")


class ProductNutritionFactory(DjangoModelFactory):
    """Factory for ProductNutrition model."""

    class Meta:
        """Meta class."""

        model = ProductNutrition

    product = factory.SubFactory(ProductFactory)
    nutrition_facts = factory.SubFactory(NutritionFactsFactory)


class AlertSubscriberFactory(DjangoModelFactory):
    """Factory for AlertSubscriber model."""

    class Meta:
        """Meta class."""

        model = AlertSubscriber

    email = factory.Faker("email")
