"""Tests for core services, selectors, and REST boundaries."""

from __future__ import annotations

from django.test import TestCase

from core.models import (
    Brand,
    Product,
)


class ProductEanTests(TestCase):
    """Coverage for the nullable unique EAN column."""

    def setUp(self) -> None:
        """Create a reusable brand."""
        self.brand = Brand.objects.create(name="growth", display_name="Growth")

    def test_products_without_ean_do_not_collide(self) -> None:
        """A blank EAN is stored as null so the unique index ignores it."""
        first = Product.objects.create(name="Whey", brand=self.brand, ean="")
        second = Product.objects.create(name="Creatine", brand=self.brand, ean="")

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.ean is None
        assert second.ean is None
