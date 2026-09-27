"""What an agent reads when it picks a related object.

An MCP client chooses an offer, a label or a category from autocomplete and
retrieve payloads, which render each object with ``str()``. A label that says
only a key forces a lookup per candidate; one that says what the object is lets
the choice be made on sight.
"""

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
)
from offers.models import Offer


class ObjectLabelTests(TestCase):
    """Each object names itself the way a curator tells it apart."""

    def test_an_offer_names_its_store_product_flavor_and_price(self) -> None:
        """Nineteen Growth offers share a name; the flavor tells them apart."""
        offer = Offer.objects.create(
            store_slug="growth",
            external_id="185-4",
            name="(TOP) Whey Protein Concentrado 1Kg",
            current_price=Decimal("194.33"),
            options=[{"name": "Sabor", "value": "Natural"}],
        )

        label = str(offer)

        for part in ("growth", "Whey Protein Concentrado", "Natural", "194.33"):
            assert part in label, label

    def test_a_delisted_offer_says_so(self) -> None:
        """An offer the store no longer sells cannot be mistaken for a live one."""
        offer = Offer.objects.create(store_slug="growth", external_id="185")
        offer.delisted_at = offer.created_at
        offer.save(update_fields=["delisted_at"])

        assert "delisted" in str(offer)

    def test_a_nutrition_profile_names_the_flavors_that_print_it(self) -> None:
        """A product's labels are told apart by flavor, not by table hash."""
        product = Product.objects.create(
            name="Whey 1kg",
            brand=Brand.objects.create(name="growth", display_name="Growth"),
            net_mass=Decimal(1000),
        )
        profile = ProductNutrition.objects.create(
            product=product,
            nutrition_facts=NutritionFacts.objects.create(serving_size=Decimal(30)),
        )
        profile.flavors.add(Flavor.objects.create(name="Natural"))

        assert "Natural" in str(profile)
        assert "Whey 1kg" in str(profile)

    def test_a_category_names_its_whole_path(self) -> None:
        """Concentrado under Whey under Proteína is chosen by its place."""
        protein = Category.add_root(name="Proteína")
        whey = protein.add_child(name="Whey")
        concentrate = whey.add_child(name="Concentrado")

        assert str(concentrate) == "Proteína › Whey › Concentrado"
