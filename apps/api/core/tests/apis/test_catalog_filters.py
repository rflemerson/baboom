"""SYNTHETIC: the catalog filters by brand, flavor and category, several at once."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from core.models import (
    Brand,
    Category,
    Flavor,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductStore,
    Store,
)
from core.tests.helpers import store_seller
from offers.models import Offer, StockStatus
from pricing.projections import ProjectionService

PRODUCTS = "/api/catalog/products/"
FILTERS = "/api/catalog/filters/"


class CatalogFilterTests(TestCase):
    """Choices are matched by name; empty choices filter nothing."""

    def setUp(self) -> None:
        """Whey (alpha, chocolate) and Pea (beta, vanilla) under Proteins."""
        Store.objects.create(name="shop", display_name="Shop", scraper_slug="shop")
        proteins = Category.add_root(name="Proteins")
        plant = proteins.add_child(name="Plant protein")
        whey = proteins.add_child(name="Whey")
        for name, brand, flavor, category, stock in (
            ("Whey", "alpha", "Chocolate", whey, StockStatus.AVAILABLE),
            ("Pea", "beta", "Vanilla", plant, StockStatus.OUT_OF_STOCK),
        ):
            product = Product.objects.create(
                name=name,
                brand=Brand.objects.create(name=brand, display_name=brand.title()),
                category=category,
                is_published=True,
            )
            profile = ProductNutrition.objects.create(
                product=product,
                nutrition_facts=NutritionFacts.objects.create(
                    serving_size=Decimal(30),
                    proteins=Decimal(24),
                ),
            )
            profile.flavors.add(Flavor.objects.create(name=flavor))
            offer = Offer.objects.create(
                seller_account=store_seller("shop"),
                store_slug="shop",
                external_id=name,
                url=f"https://shop.example/{name}",
                current_price=Decimal(100),
                current_stock_status=stock,
                options=[{"name": "Sabor", "value": flavor}],
            )
            ProductStore.objects.create(product=product, offer=offer)
        Product.objects.create(
            name="Draft",
            brand=Brand.objects.create(name="hidden", display_name="Hidden"),
            is_published=False,
        )
        ProjectionService().refresh()

    def _names(self, query: str = "") -> list[str]:
        items = self.client.get(f"{PRODUCTS}?per_page=48{query}").json()["items"]
        return sorted(item["name"] for item in items)

    def test_each_choice_filters_by_its_whole_name(self) -> None:
        """Brand, flavor and category, alone or several of one kind."""
        assert self._names("&brand=alpha&brand=beta") == ["Pea", "Whey"]
        assert self._names("&brand=alph") == []
        assert self._names("&flavor=Vanilla") == ["Pea"]
        assert self._names("&category=Whey") == ["Whey"]

    def test_a_category_keeps_its_subcategories(self) -> None:
        """Proteins holds both whey and plant protein."""
        assert self._names("&category=Proteins") == ["Pea", "Whey"]

    def test_kinds_combine_and_empty_values_are_ignored(self) -> None:
        """Different kinds narrow together; a blank value filters nothing."""
        assert self._names("&brand=alpha&flavor=Vanilla") == []
        assert self._names("&brand=&flavor=") == ["Pea", "Whey"]

    def test_stock_is_reported_and_filtered_apart_from_price(self) -> None:
        """A sold-out product keeps its price; the stock filter can hide it."""
        items = self.client.get(f"{PRODUCTS}?per_page=48").json()["items"]
        stock = {item["name"]: (item["stockStatus"], item["price"]) for item in items}

        assert stock == {
            "Whey": ("in_stock", "100.00"),
            "Pea": ("out_of_stock", "100.00"),
        }
        assert self._names("&stock=in_stock") == ["Whey"]
        assert self._names("&stock=in_stock&stock=out_of_stock") == ["Pea", "Whey"]

    def test_the_options_are_those_of_published_products(self) -> None:
        """Drafts add no option; categories come with their ancestors, by path."""
        options = self.client.get(FILTERS).json()

        assert options["brands"] == [
            {"name": "alpha", "label": "Alpha"},
            {"name": "beta", "label": "Beta"},
        ]
        assert options["flavors"] == [
            {"name": "Chocolate", "label": "Chocolate"},
            {"name": "Vanilla", "label": "Vanilla"},
        ]
        assert options["categories"] == [
            {"name": "Proteins", "label": "Proteins"},
            {"name": "Plant protein", "label": "Proteins > Plant protein"},
            {"name": "Whey", "label": "Proteins > Whey"},
        ]
