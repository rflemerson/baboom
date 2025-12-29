import json
import logging

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)

API_USER_INIT = "https://www.gsuplementos.com.br/api/v2/front/checkout/user/"
API_MENUS = "https://www.gsuplementos.com.br/api/v2/front/struct/menus/nova-home-suplementos-categorias"
API_LISTING = (
    "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
)


def run():
    # Headers from User (Script)
    headers = {
        "User-Agent": "insomnia/12.2.0",
        "app-token": "wapstore",
        "Content-Type": "application/json",
    }

    session = requests.Session()
    session.verify = False

    # 2. Listing
    print("\n2. Testing Listing (url=/proteina/)...")
    params = {"url": "/proteina/", "offset": "0", "limit": "30"}

    try:
        resp = session.get(API_LISTING, headers=headers, params=params)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # print keys to be sure
            print(f"   Keys: {data.keys()}")

            # User's Logic: data['conteudo']['produtos']
            if "conteudo" in data and "produtos" in data["conteudo"]:
                products = data["conteudo"]["produtos"]
                print(f"   -> Count: {len(products)}")
                if products:
                    print("   SUCCESS! First item:")
                    # print(json.dumps(products[0], indent=2))
                    first = products[0]
                    print(f"   Name: {first.get('nome')}")
                    print(f"   EAN keys check: 'ean' in keys: {'ean' in first}, 'gtin' in keys: {'gtin' in first}")
                    print(f"   Keys: {list(first.keys())}")
                    if 'variacoes' in first:
                         print(f"   Variacoes count: {len(first['variacoes'])}")
                         if first['variacoes']:
                             print(f"   First Var Keys: {list(first['variacoes'][0].keys())}")
            else:
                print("   'conteudo' or 'produtos' key not found.")
                print(json.dumps(data)[:500])
        else:
            print(f"   Error: {resp.text}")

    except Exception as e:
        print(f"   Listing failed: {e}")


if __name__ == "__main__":
    run()
