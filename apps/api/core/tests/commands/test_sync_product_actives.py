"""Tests for rebuilding product and combo active aggregates."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import ComboActive, Product, ProductActive, ProductComponent
from core.tests.factories import ProductFactory, ProductNutritionFactory
from core.units import to_canonical

EXPECTED_SIMPLE_ACTIVE_ROWS = 7
EXPECTED_COMPONENT_ACTIVE_ROWS = 14
COMPONENT_NET_MASS = Decimal(900)
EXPECTED_COMBO_TOTAL_MASS = to_canonical(Decimal(2160), "g")


class SyncProductActivesCommandTests(TestCase):
    """The command reconstructs all derived catalog active rows."""

    def test_command_rebuilds_simple_product_active_rows(self) -> None:
        """A product's missing derived row is recreated and reported."""
        product = ProductFactory()
        profile = ProductNutritionFactory(product=product)
        ProductActive.objects.filter(nutrition_profile=profile).delete()
        output = StringIO()

        call_command("sync_product_actives", stdout=output)

        active = ProductActive.objects.get(
            nutrition_profile=profile,
            active__slug="protein",
        )
        assert active.fraction == Decimal("0.80000000")
        assert ProductActive.objects.count() == EXPECTED_SIMPLE_ACTIVE_ROWS
        assert output.getvalue() == "Synced 7 product active rows.\n"

    def test_command_rebuilds_components_and_combo_totals(self) -> None:
        """The command rebuilds component fractions before combo totals."""
        first = ProductFactory(net_mass=to_canonical(COMPONENT_NET_MASS, "g"))
        second = ProductFactory(net_mass=to_canonical(COMPONENT_NET_MASS, "g"))
        first_profile = ProductNutritionFactory(product=first)
        second_profile = ProductNutritionFactory(product=second)
        combo = ProductFactory(kind=Product.Kind.COMBO, net_mass=None)
        ProductComponent.objects.create(parent=combo, component=first, quantity=2)
        ProductComponent.objects.create(parent=combo, component=second, quantity=1)
        ProductActive.objects.filter(
            nutrition_profile__in=[first_profile, second_profile],
        ).delete()
        ComboActive.objects.filter(combo=combo).delete()
        output = StringIO()

        call_command("sync_product_actives", stdout=output)

        assert ProductActive.objects.count() == EXPECTED_COMPONENT_ACTIVE_ROWS
        combo_active = ComboActive.objects.get(combo=combo, active__slug="protein")
        assert combo_active.total_mass == EXPECTED_COMBO_TOTAL_MASS
        assert output.getvalue() == "Synced 14 product active rows.\n"
