"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from django.test import TestCase

from core.models import (
    Brand,
    Product,
    ProductComponent,
)
from core.tests.helpers import (
    _validation_error,
)


class ProductComponentTests(TestCase):
    """Coverage for the combo assembly rules."""

    def setUp(self) -> None:
        """Create a combo and the simple products it can contain."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")
        self.combo = Product.objects.create(
            name="Starter Kit",
            brand=self.brand,
            kind=Product.Kind.COMBO,
        )
        self.whey = Product.objects.create(name="Whey", brand=self.brand)
        self.creatine = Product.objects.create(name="Creatine", brand=self.brand)

    def test_combo_accepts_simple_components(self) -> None:
        """A combo assembles simple products with quantities."""
        ProductComponent.objects.create(
            parent=self.combo,
            component=self.whey,
            quantity=2,
        )

        assert self.combo.component_links.count() == 1
        assert self.combo.is_combo is True

    def test_component_cannot_be_the_parent_itself(self) -> None:
        """Self-reference is rejected before it reaches the database."""
        error = _validation_error(
            lambda: ProductComponent.objects.create(
                parent=self.combo,
                component=self.combo,
            ),
        )

        assert "component" in error.message_dict

    def test_component_cannot_be_another_combo(self) -> None:
        """Assemblies stay one level deep, so no cycle can be built."""
        nested = Product.objects.create(
            name="Nested Kit",
            brand=self.brand,
            kind=Product.Kind.COMBO,
        )

        error = _validation_error(
            lambda: ProductComponent.objects.create(
                parent=self.combo,
                component=nested,
            ),
        )

        assert "component" in error.message_dict

    def test_simple_product_cannot_have_components(self) -> None:
        """Only combos assemble other products."""
        error = _validation_error(
            lambda: ProductComponent.objects.create(
                parent=self.whey,
                component=self.creatine,
            ),
        )

        assert "parent" in error.message_dict

    def test_combo_cannot_be_downgraded_while_it_has_components(self) -> None:
        """The kind stays consistent with the rows that depend on it."""
        ProductComponent.objects.create(parent=self.combo, component=self.whey)
        self.combo.kind = Product.Kind.SIMPLE

        error = _validation_error(self.combo.save)

        assert "kind" in error.message_dict
