"""Tests for the curated link between a catalog product and a captured offer."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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
    """A product is one package with one nutrition table; offers price it.

    Natural and the flavored whey of one page print different tables, so they
    are two products, each linked to the offers of its own flavors.
    """

    LINKED_FLAVORS = 2

    def setUp(self) -> None:
        """Create the flavored whey of a Growth page, not yet labelled."""
        self.store = Store.objects.create(
            name="Growth",
            display_name="Growth Supplements",
            scraper_slug="growth",
        )
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Whey Protein Concentrado 1 kg",
            brand=self.brand,
            net_mass=Decimal(1000),
        )

    def _label(self, product: Product, *flavors: str) -> ProductNutrition:
        """Give a product its nutrition table, printed by the given flavors."""
        profile = ProductNutrition.objects.create(
            product=product,
            nutrition_facts=NutritionFacts.objects.create(
                serving_size=Decimal(30),
                proteins=Decimal(24),
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

    def _link(self, offer: Offer, product: Product | None = None) -> ProductStore:
        """Link an offer to a product through the model rules."""
        return ProductStore.objects.create(product=product or self.product, offer=offer)

    def test_an_unlabelled_product_takes_its_offer_now(self) -> None:
        """The price and the link need not wait for the nutrition table."""
        link = self._link(self._offer("185-1", "Chocolate"))

        assert link.store == self.store

    def test_several_flavors_of_one_store_price_one_product(self) -> None:
        """Chocolate and Morango print one table, so they are one product."""
        self._label(self.product, "Chocolate", "Morango")

        self._link(self._offer("185-1", "Chocolate"))
        self._link(self._offer("185-2", "Morango"))

        assert self.product.store_links.count() == self.LINKED_FLAVORS

    def test_a_product_has_one_nutrition_table(self) -> None:
        """A second table is a second product, even on the same page."""
        self._label(self.product, "Chocolate")

        with transaction.atomic():
            error = _raised(
                lambda: self._label(self.product, "Natural"), IntegrityError
            )

        assert isinstance(error, IntegrityError)

    def test_the_printed_flavor_matches_regardless_of_case_and_accents(self) -> None:
        """A store printing NATURAL sells the flavor the catalog names Natural."""
        natural = Product.objects.create(
            name="Whey Protein Concentrado 1 kg Natural",
            brand=self.brand,
            net_mass=Decimal(1000),
        )
        self._label(natural, "Natural")

        link = self._link(self._offer("185-4", "NATURAL"), natural)

        assert link.product == natural

    def test_a_labelled_product_refuses_a_flavor_it_does_not_print(self) -> None:
        """Natural sold under the flavored table would rank the wrong protein."""
        self._label(self.product, "Chocolate", "Morango")

        error = _raised(
            lambda: self._link(self._offer("185-4", "Natural")),
            ValidationError,
        )

        assert "offer" in error.message_dict

    def test_a_labelled_product_refuses_an_offer_that_states_no_flavor(self) -> None:
        """A page-level offer is not evidence of which flavor it sells."""
        self._label(self.product, "Chocolate")

        error = _raised(lambda: self._link(self._offer("185")), ValidationError)

        assert "offer" in error.message_dict

    def test_a_simple_product_refuses_a_kit(self) -> None:
        """An offer selling several flavors at once is a combo."""
        offer = self._offer("kit")
        offer.options = [
            {"name": "Sabor", "value": "Chocolate"},
            {"name": "Sabor 2", "value": "Morango"},
        ]
        offer.save(update_fields=["options"])

        error = _raised(lambda: self._link(offer), ValidationError)

        assert "offer" in error.message_dict

    def test_a_delisted_offer_cannot_be_linked(self) -> None:
        """An offer the store no longer sells has no price to show."""
        offer = self._offer("185-1", "Chocolate")
        offer.delisted_at = timezone.now()
        offer.save(update_fields=["delisted_at"])

        error = _raised(lambda: self._link(offer), ValidationError)

        assert "offer" in error.message_dict

    def test_an_offer_from_a_store_without_a_mapping_is_rejected(self) -> None:
        """Without a store to show, the link would publish an anonymous price."""
        offer = Offer.objects.create(
            store_slug="unknown_store",
            external_id="1",
            url="https://unknown.example/1",
            current_price=Decimal(10),
        )

        error = _raised(lambda: self._link(offer), ValidationError)

        assert "offer" in error.message_dict

    def test_a_combo_is_priced_like_any_product(self) -> None:
        """A kit links to its combo, flavors and all."""
        combo = Product.objects.create(
            name="Kit Whey + Creatina",
            brand=self.brand,
            kind=Product.Kind.COMBO,
        )
        offer = self._offer("kit")
        offer.options = [
            {"name": "Sabor", "value": "Chocolate"},
            {"name": "Sabor 2", "value": "Morango"},
        ]
        offer.save(update_fields=["options"])

        assert self._link(offer, combo).store == self.store
