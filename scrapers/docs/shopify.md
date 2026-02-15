# Shopify JSON Strategy

**Applicable Brands:**
*   Dark Lab
*   Soldiers Nutrition

## Overview
Shopify stores publicly expose JSON catalog endpoints. The production strategy
uses a 3-step flow:
1. `collections.json` to discover category handles
2. `collections/{handle}/products.json` for paginated product listing
3. `products/{handle}.js` for full product context (variants/options/images)

## Endpoint Patterns
* `https://{domain}/collections.json`
* `https://{domain}/collections/{handle}/products.json`
* `https://{domain}/products/{handle}.js`

## Request Parameters
*   `limit`: (Integer) Items per page. Max is **250**.
*   `page`: (Integer) Page number, starting at 1.

**Pagination Algorithm:**
```python
for category in collections:
    page = 1
    while True:
        params = {"limit": 250, "page": page}
        resp = requests.get(f"/collections/{category}/products.json", params=params)
        products = resp.json().get("products", [])
        if not products:
            break
        for product in products:
            handle = product.get("handle")
            details = requests.get(f"/products/{handle}.js").json() if handle else product
        if len(products) < 250:
            break
        page += 1
```

## JSON Response Structure
Listing endpoints return a Dictionary with a `products` key.
Detail endpoint returns one product object with full variant metadata.

```json
{
  "products": [
    {
      "id": 67890,
      "title": "Whey Protein Isolate",
      "handle": "whey-protein-isolate",
      "vendor": "Dark Lab",
      "product_type": "Supplements",
      "variants": [
        {
          "id": 112233,
          "title": "Chocolate / 900g",
          "price": "149.90",
          "available": true,
          "sku": "DL-WHEY-CHO"
        }
      ],
      "images": [ ... ]
    }
  ]
}
```

## Key Parsing Rules
1.  **Product ID**: `id` (Root level).
2.  **Variants**: `variants` array. Contains specific price/stock info.
    *   *Strategy*: Iterate variants or pick first available variant.
    *   **Price**:
        * In `/collections/.../products.json`: commonly decimal string (e.g. `"89.90"`).
        * In `/products/{handle}.js`: can be integer cents (e.g. `1390` -> `13.90`).
    *   **Stock**: `variants[].available` (Boolean). Shopify rarely exposes exact count publicly, but precise availability status is reliable.
3.  **URL**: Constructed from `handle`: `https://{domain}/products/{handle}`.
4.  **Context**: Persist `options`, `variants`, and `images` JSON for downstream pipeline usage.

## Implementation Examples
*   `scrapers/spiders/dark_lab.py`
*   `scrapers/spiders/soldiers.py`
