
import requests
import json
import urllib3

urllib3.disable_warnings()

URL = "https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category"
HEADERS = {
    "User-Agent": "insomnia/12.2.0",
    "app-token": "wapstore",
    "Accept": "application/json",
    "Origin": "https://www.gsuplementos.com.br",
    "Referer": "https://www.gsuplementos.com.br/"
}
PARAMS = {
    "url": "/vegano/",
    "offset": 0,
    "limit": 3
}

def inspect():
    print(f"Fetching {URL}...")
    try:
        resp = requests.get(URL, headers=HEADERS, params=PARAMS, verify=False, timeout=10)
        print(f"Request URL: {resp.url}")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            products = data.get("data", {}).get("list", [])
            print(f"Found {len(products)} products.")
            if products:
                # Print first product keys and full structure
                first = products[0]
                print(json.dumps(first, indent=2))
        else:
            print(resp.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
