# Shopify JSON Strategy

**Applicable Brands:**
*   Dark Lab

## Overview
Shopify stores publicly expose a JSON representation of their catalog via the `products.json` endpoint. This is a standard feature of the Shopify platform and is incredibly reliable for scraping.

## Endpoint Pattern
`https://{domain}/products.json`

## Request Parameters
*   `limit`: (Integer) Items per page. Max is **250**.
*   `page`: (Integer) Page number, starting at 1.

**Pagination Algorithm:**
```python
page = 1
limit = 250
while True:
    params = {"limit": limit, "page": page}
    resp = requests.get(url, params=params)
    
    data = resp.json()
    products = data.get("products", [])
    
    if not products:
        break
        
    page += 1
```

## JSON Response Structure
The response is a Dictionary with a `products` key.

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
    *   *Strategy*: Iterate variants or pick the first one.
    *   **Price**: `variants[].price` (String).
    *   **Stock**: `variants[].available` (Boolean). Shopify rarely exposes exact count publicly, but precise availability status is reliable.
3.  **URL**: Constructed from `handle`: `https://{domain}/products/{handle}`.

## Implementation Examples
*   `scrapers/spiders/dark_lab.py`
