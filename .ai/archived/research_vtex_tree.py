import logging

import requests

logging.basicConfig(level=logging.INFO)

STORES = [
    {"name": "Max Titanium", "base_url": "https://www.maxtitanium.com.br"},
    {"name": "Integral Medica", "base_url": "https://www.integralmedica.com.br"},
    {"name": "Dux Nutrition", "base_url": "https://www.duxhumanhealth.com"},
    # Probiotica might also work
    {"name": "Probiotica", "base_url": "https://www.probiotica.com.br"},
]


def get_tree(store_name, base_url):
    url = f"{base_url}/api/catalog_system/pub/category/tree/3"
    print(f"\n--- {store_name} ---")
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            categories = resp.json()
            print(f"Total Top-Level Categories: {len(categories)}")

            # Recursive printer
            def print_tree(cats, level=0):
                for c in cats:
                    indent = "  " * level
                    print(f"{indent}- [{c['id']}] {c['name']} ({c['url']})")
                    # Limit output for demo
                    if level < 2 and "children" in c:
                        print_tree(c["children"], level + 1)

            # Filter to show some interesting ones
            print("Tree Sample:")
            print_tree(categories[:5])
        else:
            print(f"Failed: {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    for store in STORES:
        get_tree(store["name"], store["base_url"])
