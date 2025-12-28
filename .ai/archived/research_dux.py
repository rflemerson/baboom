import json
import logging

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Likely URL structure (VTEX ?)
CATEGORY_URL = "https://www.duxhumanhealth.com/proteinas"
# Optimistic VTEX API Check
API_TEST_URL = "https://www.duxhumanhealth.com/api/catalog_system/pub/products/search/proteinas?_from=0&_to=5"


def run():
    print(f"1. Testing API: {API_TEST_URL}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(API_TEST_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            print("\n=== VTEX API SUCCESS (Search: 'Proteinas') ===")
            data = response.json()
            print(f"Items found: {len(data)}")
            if len(data) > 0:
                print(json.dumps(data[0], default=str)[:1000])
        else:
            print(f"VTEX API Failed: {response.status_code}")
    except Exception as e:
        print(f"API Check Error: {e}")

    try:
        print(f"\n2. Checking Platforms on {CATEGORY_URL}...")
        response = requests.get(CATEGORY_URL, headers=headers, timeout=15)
        content = response.text
        if "vtex" in content:
            print("Detected 'vtex' in HTML.")
        if "shopify" in content:
            print("Detected 'shopify' in HTML.")
        if "nuvemshop" in content:
            print("Detected 'nuvemshop' in HTML.")

    except Exception as e:
        print(f"HTML Check Error: {e}")


if __name__ == "__main__":
    run()
