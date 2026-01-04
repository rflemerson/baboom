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
    class Meta:
        model = Brand

    name = factory.Sequence(lambda n: f"brand-{n}")
    display_name = factory.Sequence(lambda n: f"Brand {n}")
    description = factory.Faker("paragraph")


class StoreFactory(DjangoModelFactory):
    class Meta:
        model = Store

    name = factory.Sequence(lambda n: f"store-{n}")
    display_name = factory.Sequence(lambda n: f"Store {n}")
    description = factory.Faker("paragraph")


class FlavorFactory(DjangoModelFactory):
    class Meta:
        model = Flavor

    name = factory.Sequence(lambda n: f"flavor-{n}")
    description = factory.Faker("sentence")


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"tag-{n}")
    description = factory.Faker("sentence")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to use treebeard's add_root method."""
        return model_class.add_root(**kwargs)


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"category-{n}")
    description = factory.Faker("sentence")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to use treebeard's add_root method."""
        return model_class.add_root(**kwargs)


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    brand = factory.SubFactory(BrandFactory)
    description = factory.Faker("paragraph")
    weight = factory.Faker("random_int", min=100, max=2000)
    packaging = Product.Packaging.CONTAINER


class ProductStoreFactory(DjangoModelFactory):
    class Meta:
        model = ProductStore

    product = factory.SubFactory(ProductFactory)
    store = factory.SubFactory(StoreFactory)
    product_link = factory.Faker("url")


class ProductPriceHistoryFactory(DjangoModelFactory):
    class Meta:
        model = ProductPriceHistory

    store_product_link = factory.SubFactory(ProductStoreFactory)
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)


class NutritionFactsFactory(DjangoModelFactory):
    class Meta:
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
    class Meta:
        model = ProductNutrition

    product = factory.SubFactory(ProductFactory)
    nutrition_facts = factory.SubFactory(NutritionFactsFactory)


class AlertSubscriberFactory(DjangoModelFactory):
    class Meta:
        model = AlertSubscriber

    email = factory.Faker("email")
