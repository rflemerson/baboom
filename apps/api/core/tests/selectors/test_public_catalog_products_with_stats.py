"""Tests for the public catalog selector annotations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from django.test import TestCase
from django.utils import timezone

from core.dtos import CatalogProductsFilters
from core.models import (
    Brand,
    NutritionFacts,
    Product,
    ProductNutrition,
    ProductPriceHistory,
    ProductStore,
    Store,
)
from core.selectors import public_catalog_products, public_catalog_products_with_stats


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
        assert round(p.price_per_protein_gram, 3) == Decimal("0.125")

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
        assert result.price_per_protein_gram is None
        assert result.external_link is None

    def test_latest_price_and_external_link_use_same_history_row_on_timestamp_tie(
        self,
    ) -> None:
        """Ensure latest price annotations stay consistent under collected_at ties."""
        second_store = Store.objects.create(
            name="Second Store",
            display_name="Second Store",
        )
        second_link = ProductStore.objects.create(
            product=self.product,
            store=second_store,
            product_link="http://example.com/second",
        )

        first_history = ProductPriceHistory.objects.create(
            store_product_link=self.link,
            price=Decimal("100.00"),
        )
        second_history = ProductPriceHistory.objects.create(
            store_product_link=second_link,
            price=Decimal("150.00"),
        )
        tied_timestamp = timezone.now()
        ProductPriceHistory.objects.filter(
            id__in=[first_history.id, second_history.id],
        ).update(collected_at=tied_timestamp)

        product = cast(
            "Any | None",
            public_catalog_products_with_stats().get(pk=self.product.pk),
        )

        if product is None:
            self.fail("Product not found")

        assert product.last_price == Decimal("150.00")
        assert product.external_link == "http://example.com/second"

    def test_catalog_uses_most_protein_dense_nutrition_profile(self) -> None:
        """Ensure catalog metrics use the most protein-dense nutrition profile."""
        denser_profile = NutritionFacts.objects.create(
            serving_size_grams=30,
            proteins=Decimal("27.0"),
            carbohydrates=0,
            total_fats=0,
            description="Isolate profile",
            energy_kcal=120,
        )
        ProductNutrition.objects.create(
            product=self.product,
            nutrition_facts=denser_profile,
        )

        product = cast(
            "Any | None",
            public_catalog_products_with_stats().get(pk=self.product.pk),
        )

        if product is None:
            self.fail("Product not found")

        assert product.concentration == Decimal("90.0")
        assert product.total_protein == Decimal("900.00")
        assert round(product.price_per_protein_gram, 3) == Decimal("0.111")

    def test_catalog_sorting_is_stable_when_metric_values_tie(self) -> None:
        """Ensure catalog sorting uses a stable fallback under metric ties."""
        alpha_brand = Brand.objects.create(name="Alpha", display_name="Alpha")
        beta_brand = Brand.objects.create(name="Beta", display_name="Beta")
        alpha = Product.objects.create(
            name="Whey A",
            brand=alpha_brand,
            weight=1000,
            is_published=True,
        )
        beta = Product.objects.create(
            name="Whey B",
            brand=beta_brand,
            weight=1000,
            is_published=True,
        )

        for product in (alpha, beta):
            ProductNutrition.objects.create(
                product=product,
                nutrition_facts=self.nutrition,
            )

        alpha_store = ProductStore.objects.create(
            product=alpha,
            store=self.store,
            product_link="http://example.com/alpha",
        )
        beta_store = ProductStore.objects.create(
            product=beta,
            store=self.store,
            product_link="http://example.com/beta",
        )
        ProductPriceHistory.objects.create(
            store_product_link=alpha_store,
            price=Decimal("100.00"),
        )
        ProductPriceHistory.objects.create(
            store_product_link=beta_store,
            price=Decimal("100.00"),
        )

        items = list(
            public_catalog_products(
                CatalogProductsFilters(sort_by="last_price", sort_dir="asc"),
            ).values_list("brand__name", "name"),
        )

        assert items[:2] == [("Alpha", "Whey A"), ("Beta", "Whey B")]
