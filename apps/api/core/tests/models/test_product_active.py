"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from core.models import (
    Active,
    Brand,
    NutritionActive,
    NutritionFacts,
    Product,
    ProductActive,
    ProductNutrition,
)


class ProductActiveTests(TestCase):
    """Coverage for concentrations derived from nutrition data."""

    def setUp(self) -> None:
        """Create a product with one label and a non-macro active."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Pre Workout",
            brand=self.brand,
            net_mass=Decimal(300),
        )
        self.caffeine = Active.objects.create(
            name="Caffeine",
            slug="caffeine",
            display_unit="mg",
        )
        self.facts = NutritionFacts.objects.create(
            serving_size=Decimal(10),
            proteins=Decimal("2.0"),
        )

    def test_macro_and_label_actives_are_derived_together(self) -> None:
        """Scalar columns and label rows both produce concentrations."""
        NutritionActive.objects.create(
            nutrition_facts=self.facts,
            active=self.caffeine,
            amount=Decimal(200),
            declared_unit="mg",
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )

        protein = ProductActive.objects.get(
            nutrition_profile__product=self.product,
            active__slug="protein",
        )
        caffeine = ProductActive.objects.get(
            nutrition_profile__product=self.product,
            active=self.caffeine,
        )
        assert protein.fraction == Decimal("0.20000000")
        assert caffeine.fraction == Decimal("0.02000000")

    def test_source_unit_is_respected(self) -> None:
        """Sodium is printed in milligrams, unlike the macros around it."""
        self.facts.sodium = Decimal(50)
        self.facts.save()
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )

        sodium = ProductActive.objects.get(
            nutrition_profile__product=self.product,
            active__slug="sodium",
        )
        assert sodium.fraction == Decimal("0.00500000")

    def test_non_mass_units_carry_no_concentration(self) -> None:
        """A value in IU cannot be converted, so it produces no row."""
        vitamin = Active.objects.create(
            name="Vitamin D",
            slug="vitamin-d",
            display_unit="IU",
        )
        NutritionActive.objects.create(
            nutrition_facts=self.facts,
            active=vitamin,
            amount=Decimal(400),
            declared_unit="IU",
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )

        assert not ProductActive.objects.filter(
            nutrition_profile__product=self.product,
            active=vitamin,
        ).exists()

    def test_unlinking_a_profile_drops_its_concentrations(self) -> None:
        """Derived rows follow the nutrition profiles they came from."""
        profile = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )
        assert ProductActive.objects.filter(
            nutrition_profile__product=self.product,
        ).exists()

        profile.delete()

        assert not ProductActive.objects.filter(
            nutrition_profile__product=self.product,
        ).exists()

    def test_profiles_never_borrow_missing_actives_from_each_other(self) -> None:
        """A missing measurement in one label stays missing after synchronization."""
        NutritionActive.objects.create(
            nutrition_facts=self.facts,
            active=self.caffeine,
            amount=Decimal(200),
            declared_unit="mg",
        )
        first = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )
        other_facts = NutritionFacts.objects.create(
            serving_size=Decimal(10),
            proteins=Decimal(5),
        )
        second = ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=other_facts,
        )
        fractions = dict(
            ProductActive.objects.filter(
                nutrition_profile__product=self.product,
                active__slug="protein",
            ).values_list("nutrition_profile_id", "fraction"),
        )
        assert fractions == {first.pk: Decimal("0.2"), second.pk: Decimal("0.5")}
        assert not second.actives.filter(active=self.caffeine).exists()
        self.facts.proteins = Decimal(1)
        self.facts.save()
        assert first.actives.get(active__slug="protein").fraction == Decimal("0.1")
        assert second.actives.get(active__slug="protein").fraction == Decimal("0.5")
        ProductNutrition.objects.filter(pk=second.pk).delete()
        assert not ProductActive.objects.filter(nutrition_profile_id=second.pk).exists()
        assert first.actives.filter(active=self.caffeine).exists()


class LabelUnitTests(TestCase):
    """Values are written exactly as the label prints them.

    The curator copies numbers from the package; the unit a field is printed in
    belongs to the field, so the arithmetic, not the operator, converts.
    """

    def setUp(self) -> None:
        """Create a whey label as it is printed: grams, and sodium in mg."""
        brand = Brand.objects.create(name="growth", display_name="Growth")
        self.product = Product.objects.create(
            name="Whey",
            brand=brand,
            net_mass=Decimal(1000),
        )
        self.facts = NutritionFacts.objects.create(
            serving_size=Decimal(30),
            proteins=Decimal(24),
            sodium=Decimal(47),
        )

    def _fraction(self, slug: str) -> Decimal:
        """Return the derived fraction of one active for the product."""
        return ProductActive.objects.get(
            nutrition_profile__product=self.product,
            active__slug=slug,
        ).fraction

    def test_sodium_printed_in_mg_is_measured_against_a_serving_in_grams(
        self,
    ) -> None:
        """47 mg of sodium in a 30 g serving is a trace, not most of the scoop."""
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )

        assert self._fraction("protein") == Decimal("0.80000000")
        assert self._fraction("sodium") == Decimal("0.00156667")

    def test_a_label_active_keeps_the_amount_printed_in_micrograms(self) -> None:
        """2.4 mcg is stored as 2.4, not rounded away by a canonical conversion."""
        vitamin = Active.objects.create(
            name="Vitamin B12",
            slug="vitamin-b12",
            display_unit="mcg",
        )
        entry = NutritionActive.objects.create(
            nutrition_facts=self.facts,
            active=vitamin,
            amount=Decimal("2.4"),
            declared_unit="mcg",
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.facts,
        )

        entry.refresh_from_db()
        assert entry.amount == Decimal("2.400")
        assert self._fraction("vitamin-b12") == Decimal("0.00000008")
