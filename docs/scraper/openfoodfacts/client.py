import logging
import json
import argparse
from typing import Optional, Dict, Any
from openfoodfacts import API, APIConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

class OpenFoodFactsClient:
    def __init__(self):
        # User-Agent is mandatory for Open Food Facts API
        user_agent = "Baboom/0.1.0 (dev@baboom.com)"
        self.api = API(user_agent=user_agent, country="br")

    def get_product_by_ean(self, ean: str) -> Optional[Dict[str, Any]]:
        """
        Fetch product details by EAN (barcode).
        Returns a dictionary with relevant fields or None if not found.
        """
        logger.info(f"Searching for EAN: {ean}")
        try:
            product_data = self.api.product.get(ean)
            
            if not product_data:
                logger.warning(f"Product not found for EAN: {ean}")
                return None

            return self._parse_product(product_data)
            
        except Exception as e:
            logger.error(f"Error fetching product {ean}: {e}")
            return None

    def _parse_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts relevant fields from the raw API response.
        """
        # The SDK returns the product dictionary directly if successful
        code = data.get('code')
        product = data # The root object seems to be the product itself in some SDK versions, 
                       # but let's handle the standard JSON structure where 'product' key might exist
                       # if we were using raw requests. The SDK usually returns the product dict directly.
        
        # Check if 'status' field exists (raw API behavior) or if it's direct dict
        if 'product' in data:
            product = data['product']

        return {
            "code": code,
            "product_name": product.get('product_name'),
            "brands": product.get('brands'),
            "quantity": product.get('quantity'),
            "categories": product.get('categories'),
            "labels": product.get('labels'),
            "image_url": product.get('image_url'),
            "image_nutrition_url": product.get('image_nutrition_url'),
            "image_ingredients_url": product.get('image_ingredients_url'),
            "nutriscore_grade": product.get('nutriscore_grade'),
            "nova_group": product.get('nova_group'),
            "ecoscore_grade": product.get('ecoscore_grade'),
            "ingredients_text": product.get('ingredients_text'),
            "nutriments": self._filter_nutriments(product.get('nutriments', {})),
            "serving_size": product.get('serving_size'),
            "serving_quantity": product.get('serving_quantity'),
        }

    def _filter_nutriments(self, nutriments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filters the vast nutriments dictionary to keep key macro/micronutrients.
        """
        whitelist = [
            "energy-kcal_100g",
            "energy-kcal_serving",
            "proteins_100g",
            "proteins_serving",
            "carbohydrates_100g",
            "carbohydrates_serving",
            "sugars_100g",
            "sugars_serving",
            "fat_100g",
            "fat_serving",
            "saturated-fat_100g",
            "saturated-fat_serving",
            "fiber_100g",
            "fiber_serving",
            "sodium_100g",
            "sodium_serving",
            "salt_100g",
            "salt_serving",
        ]
        return {k: v for k, v in nutriments.items() if k in whitelist}

def main():
    parser = argparse.ArgumentParser(description="Test Open Food Facts API by EAN")
    parser.add_argument("ean", help="The EAN (barcode) of the product to search")
    args = parser.parse_args()

    client = OpenFoodFactsClient()
    result = client.get_product_by_ean(args.ean)

    if result:
        print("\n" + "="*40)
        print(f" PRODUCT FOUND: {result.get('product_name')}")
        print("="*40)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\nProduct not found or error occurred.")

if __name__ == "__main__":
    main()
