from decimal import Decimal

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


class ProductStatsTest(TestCase):
    def setUp(self):
        # 1. Setup Base Data
        self.brand = Brand.objects.create(name="Test Brand", display_name="Test Brand")
        self.store = Store.objects.create(name="Test Store", display_name="Test Store")

        # 2. Create Product (1kg = 1000g)
        self.product = Product.objects.create(
            name="Whey Protein",
            brand=self.brand,
            weight=1000,
        )

        # 3. Create Nutrition Facts
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
            product=self.product, nutrition_facts=self.nutrition
        )

        # 4. Create Price
        # Price: R$ 100.00
        self.link = ProductStore.objects.create(
            product=self.product, store=self.store, product_link="http://example.com"
        )
        ProductPriceHistory.objects.create(
            store_product_link=self.link, price=Decimal("100.00")
        )

    def test_protein_calculations(self):
        """
        Verifies if with_stats() correctly calculates:
        - Concentration (should be 80.0%)
        - Total Protein in package (Should be 800g for a 1kg package)
        - Price per gram of protein (R$ 100 / 800g = R$ 0.125)
        """
        # Act
        p = Product.objects.with_stats().first()

        # Assert
        self.assertIsNotNone(p)

        # 1. Concentration: (24g / 30g) * 100 = 80.0%
        self.assertEqual(p.concentration, Decimal("80.0"))

        # 2. Total Protein: (1000g weight * 24g prot) / 30g serving = 800g
        self.assertEqual(p.total_protein, Decimal("800.00"))

        # 3. Price per Gram Protein: R$ 100.00 / 800g = R$ 0.125
        # Note: Database might round depending on precision, checking 2 places
        self.assertEqual(round(p.price_per_gram, 3), Decimal("0.125"))

    def test_missing_price_handling(self):
        """Ensure products without price don't crash the queryset"""
        # Create a product without price
        p2 = Product.objects.create(name="No Price Whey", brand=self.brand, weight=500)

        # Act
        qs = Product.objects.with_stats().filter(pk=p2.pk)
        result = qs.first()

        # Assert
        self.assertIsNotNone(result)
        self.assertIsNone(result.last_price)
        self.assertIsNone(result.price_per_gram)
