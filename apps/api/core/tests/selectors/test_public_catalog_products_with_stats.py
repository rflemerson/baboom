"""Tests for the public catalog selector annotations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from django.test import TestCase

from core.models import (
    Brand,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
)
from core.selectors import public_catalog_products_with_stats


class ProductStatsTest(TestCase):
    """Tests for the public catalog selector annotations."""

    def setUp(self) -> None:
        """Set up test data."""
        self.brand = Brand.objects.create(name="Test Brand", display_name="Test Brand")
        self.store = Store.objects.create(name="Test Store", display_name="Test Store")

        self.product = Product.objects.create(
            name="Whey Protein",
            brand=self.brand,
            weight=1000,
        )

        # Scenario: 30g serving has 24g protein (80% concentration)
        self.nutrition = NutritionFacts.objects.create(
            serving_size_grams=30,
            proteins=Decimal("24.0"),
            carbohydrates=0,
            total_fats=0,
            description="Standard Whey",
            energy_kcal=120,
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=self.nutrition,
        )

        # Price: R$ 100.00
        self.link = ProductStore.objects.create(
            product=self.product,
            store=self.store,
            product_link="http://example.com",
        )
        ProductPriceHistory.objects.create(
            store_product_link=self.link,
            price=Decimal("100.00"),
        )

    def test_protein_calculations(self) -> None:
        """Verify if the public catalog selector correctly calculates derived fields.

        - Concentration (should be 80.0%)
        - Total Protein in package (Should be 800g for a 1kg package)
        - Price per gram of protein (R$ 100 / 800g = R$ 0.125)
        """
        # Act
        p = cast("Any | None", public_catalog_products_with_stats().first())

        # Assert
        if p is None:
            self.fail("Product not found")

        assert p.concentration == Decimal("80.0")

        assert p.total_protein == Decimal("800.00")

        # Note: Database might round depending on precision, checking 2 places
        assert round(p.price_per_gram, 3) == Decimal("0.125")

        assert p.external_link == "http://example.com"

    def test_missing_price_handling(self) -> None:
        """Ensure products without price don't crash the queryset."""
        # Create a product without price
        p2 = Product.objects.create(name="No Price Whey", brand=self.brand, weight=500)

        # Act
        qs = public_catalog_products_with_stats().filter(pk=p2.pk)
        result = cast("Any | None", qs.first())

        # Assert
        if result is None:
            self.fail("Product not found")

        assert result.last_price is None
        assert result.price_per_gram is None
        assert result.external_link is None
