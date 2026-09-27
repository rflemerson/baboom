"""Tests for the curated link between a catalog row and a captured offer."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Brand,
    Flavor,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductStore,
    Store,
)
from core.tests.helpers import _raised
from offers.models import Offer


class ProductStoreLinkTests(TestCase):
    """A link binds one nutrition profile of a product to one captured offer.

    The catalog ranks a product per nutrition profile, and a store sells one
    flavor per offer, so the link sits where both meet: the profile whose label
    that flavor prints.
    """

    LINKED_FLAVORS = 3

    def setUp(self) -> None:
        """Create a whey with a Natural label and a flavored label."""
        self.store = Store.objects.create(
            name="Growth",
            display_name="Growth Supplements",
            scraper_slug="growth",
        )
        brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Whey Concentrado 1kg",
            brand=brand,
            net_mass=Decimal(1000),
        )
        self.natural = self._profile("Natural", proteins=24)
        self.flavored = self._profile("Chocolate", "Morango", proteins=21)

    def _profile(self, *flavors: str, proteins: int) -> ProductNutrition:
        """Create a nutrition profile printed by the given flavors."""
        profile = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(proteins),
            ),
        )
        profile.flavors.set(
            [Flavor.objects.get_or_create(name=name)[0] for name in flavors],
        )
        return profile

    def _offer(self, external_id: str, flavor: str | None = None) -> Offer:
        """Create a captured Growth offer stating the flavor it sells."""
        return Offer.objects.create(
            store_slug="growth",
            external_id=external_id,
            name="Whey Protein Concentrado 1Kg",
            url=f"https://growth.example/whey?variant={external_id}",
            current_price=Decimal("194.33"),
            options=[] if flavor is None else [{"name": "Sabor", "value": flavor}],
        )

    def _link(
        self,
        offer: Offer,
        profile: ProductNutrition | None,
    ) -> ProductStore:
        """Link an offer to a profile of the whey through the model rules."""
        return ProductStore.objects.create(
            product=self.product,
            nutrition_profile=profile,
            offer=offer,
        )

    def test_the_store_comes_from_the_offer(self) -> None:
        """The curator names the offer; the store is the one that sells it."""
        link = self._link(self._offer("185:4", "Natural"), self.natural)

        assert link.store == self.store

    def test_each_flavor_of_one_store_links_to_its_own_label(self) -> None:
        """Natural and Chocolate from the same store coexist on one product."""
        self._link(self._offer("185:4", "Natural"), self.natural)
        self._link(self._offer("185:1", "Chocolate"), self.flavored)
        self._link(self._offer("185:2", "Morango"), self.flavored)

        assert self.product.store_links.count() == self.LINKED_FLAVORS

    def test_the_printed_flavor_matches_regardless_of_case_and_accents(self) -> None:
        """A store printing NATURAL sells the flavor the catalog names Natural."""
        link = self._link(self._offer("185:4", "NATURAL"), self.natural)

        assert link.nutrition_profile == self.natural

    def test_an_offer_cannot_borrow_another_flavor_label(self) -> None:
        """Chocolate sold with the Natural label would rank the wrong protein."""
        error = _raised(
            lambda: self._link(self._offer("185:1", "Chocolate"), self.natural),
            ValidationError,
        )

        assert "offer" in error.message_dict

    def test_an_offer_that_states_no_flavor_cannot_fill_a_flavored_label(
        self,
    ) -> None:
        """A page-level offer is not evidence of which flavor it sells."""
        error = _raised(
            lambda: self._link(self._offer("185"), self.natural),
            ValidationError,
        )

        assert "offer" in error.message_dict

    def test_a_simple_product_needs_the_label_the_offer_sells(self) -> None:
        """Without a profile the row has no protein to rank the price by."""
        error = _raised(
            lambda: self._link(self._offer("185:4", "Natural"), None),
            ValidationError,
        )

        assert "nutrition_profile" in error.message_dict

    def test_the_label_must_belong_to_the_product(self) -> None:
        """A profile of another product would price the wrong catalog row."""
        other = Product.objects.create(
            name="Isolado",
            brand=self.product.brand,
            net_mass=Decimal(900),
        )

        error = _raised(
            lambda: ProductStore.objects.create(
                product=other,
                nutrition_profile=self.natural,
                offer=self._offer("185:4", "Natural"),
            ),
            ValidationError,
        )

        assert "nutrition_profile" in error.message_dict

    def test_a_delisted_offer_cannot_be_linked(self) -> None:
        """An offer the store no longer sells has no price to show."""
        offer = self._offer("185:4", "Natural")
        offer.delisted_at = timezone.now()
        offer.save(update_fields=["delisted_at"])

        error = _raised(lambda: self._link(offer, self.natural), ValidationError)

        assert "offer" in error.message_dict

    def test_an_offer_from_a_store_without_a_mapping_is_rejected(self) -> None:
        """Without a store to show, the link would publish an anonymous price."""
        offer = Offer.objects.create(
            store_slug="unknown_store",
            external_id="1",
            url="https://unknown.example/1",
            current_price=Decimal(10),
        )
        self.natural.flavors.clear()

        error = _raised(lambda: self._link(offer, self.natural), ValidationError)

        assert "offer" in error.message_dict

    def test_a_combo_is_priced_without_a_label(self) -> None:
        """A combo ranks through its components, so it has no label to name."""
        combo = Product.objects.create(
            name="Kit Whey + Creatina",
            brand=self.product.brand,
            kind=Product.Kind.COMBO,
        )
        link = ProductStore.objects.create(
            product=combo,
            nutrition_profile=None,
            offer=self._offer("kit-1"),
        )

        assert link.store == self.store
