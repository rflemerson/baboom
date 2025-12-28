import base64
import json

import requests

# Original URL template
# We need to construct the `extensions` parameter carefully.
BASE_URL = "https://www.blackskullusa.com.br/_v/segment/graphql/v1"


def fetch_products(start=0, end=9):
    # 1. Create the Variables JSON
    variables_dict = {
        "hideUnavailableItems": False,
        "category": "",  # Empty for everything? Or specific ID?
        "specificationFilters": [],
        "orderBy": "OrderByTopSaleDESC",
        "from": start,
        "to": end,
        "shippingOptions": [],
        "variant": "",
        "advertisementOptions": {
            "showSponsored": False,
            "sponsoredCount": 0,
            "repeatSponsoredProducts": False,
            "advertisementPlacement": "home_shelf",
        },
    }

    # 2. Stringify and Base64 Encode variables
    vars_json = json.dumps(variables_dict, separators=(",", ":"))  # Compact JSON
    vars_b64 = base64.b64encode(vars_json.encode("utf-8")).decode("utf-8")

    # 3. Create the Full Extensions JSON
    extensions_dict = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": "ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22",
            "sender": "vtex.store-resources@0.x",
            "provider": "vtex.search-graphql@0.x",
        },
        "variables": vars_b64,
    }

    extensions_json = json.dumps(extensions_dict, separators=(",", ":"))

    # 4. Params
    params = {
        "workspace": "newblackpdp",
        "maxAge": "short",
        "appsEtag": "remove",
        "domain": "store",
        "locale": "pt-BR",
        "operationName": "Products",
        "variables": "{}",  # Verify if this needs to be empty dict
        "extensions": extensions_json,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept": "*/*",
        "content-type": "application/json",
    }

    print(f"Fetching {start}-{end}...")
    try:
        resp = requests.get(BASE_URL, params=params, headers=headers)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            # Navigate to products
            # Structure usually: data -> products -> items?
            if "data" in data and "products" in data["data"]:
                prods = data["data"]["products"]
                # Sometimes it returns null if error
                if prods is None:
                    print("Products is null. Check errors?")
                    if "errors" in data:
                        print(data["errors"])
                else:
                    # Debug type
                    print(f"Products type: {type(prods)}")
                    if isinstance(prods, list):
                        print(f"Found {len(prods)} items (List)")
                        if prods:
                            print(json.dumps(prods[0], indent=2))
                    elif isinstance(prods, dict):
                        print(f"Products dict keys: {prods.keys()}")
                        items = prods.get("products", [])
                        if not items and "items" in prods:
                            items = prods["items"]
                        print(f"Found {len(items)} items")
                        if items:
                            print(json.dumps(items[0], indent=2))
            else:
                print(f"Unexpected JSON: {list(data.keys())}")
        else:
            print(resp.text[:500])

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    fetch_products(0, 9)
