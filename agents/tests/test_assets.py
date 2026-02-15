from django.test import SimpleTestCase

from agents.assets import _build_nutrition_payload, _slugify, _to_graphql_stock_status


class TestAssetsHelpers(SimpleTestCase):
    """Tests for small helper functions used by Dagster assets."""

    def test_slugify(self):
        """Normalizes names to stable slugs."""
        self.assertEqual(_slugify("Whey Protein 100%"), "whey-protein-100")
        self.assertEqual(_slugify("###"), "item")

    def test_stock_status_mapping(self):
        """Maps scraper statuses to GraphQL enum values."""
        self.assertEqual(_to_graphql_stock_status("A"), "AVAILABLE")
        self.assertEqual(_to_graphql_stock_status("LAST_UNITS"), "LAST_UNITS")
        self.assertEqual(_to_graphql_stock_status("unknown"), "AVAILABLE")

    def test_build_nutrition_payload(self):
        """Builds nutrition payload with converted numeric fields."""
        payload = _build_nutrition_payload(
            {
                "variant_name": "Chocolate",
                "flavor_names": ["Chocolate"],
                "nutrition_facts": {
                    "serving_size_grams": 30,
                    "energy_kcal": 120,
                    "proteins": 20,
                    "carbohydrates": 4,
                    "total_sugars": 2,
                    "added_sugars": 0,
                    "total_fats": 2,
                    "saturated_fats": 1,
                    "trans_fats": 0,
                    "dietary_fiber": 1,
                    "sodium": 50,
                    "micronutrients": [
                        {"name": "vitamin-c", "value": 45, "unit": "mg"}
                    ],
                },
            }
        )

        self.assertEqual(len(payload), 1)
        facts = payload[0]["nutritionFacts"]
        self.assertEqual(facts["description"], "Chocolate")
        self.assertEqual(facts["energyKcal"], 120)
        self.assertEqual(payload[0]["flavorNames"], ["Chocolate"])
