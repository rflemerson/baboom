# VTEX Legacy / Search API Strategy

**Applicable Brands:**
*   Integral Medica
*   Max Titanium
*   Probiotica
*   Dux Nutrition

## Overview
These stores operate on the classic VTEX infrastructure (or expose the standard Search API compatibility layer). The `api/catalog_system/pub/products/search` endpoint is the "Gold Standard" for scraping VTEX stores without headless browsers.

## Endpoint Pattern
The base URL varies, but the path is consistent:
`https://{domain}/api/catalog_system/pub/products/search`

## Request Parameters
*   `_from`: (Integer) Start index (0-based).
*   `_to`: (Integer) End index (Inclusive).
*   `fq`: (Optional) Filter Query. E.g., `C:123/456` for specific categories.

**Pagination Algorithm:**
```python
start = 0
step = 50
while True:
    end = start + step - 1
    params = {"_from": start, "_to": end}
    resp = requests.get(url, params=params)

    # VTEX quirks:
    # 1. Status 206 (Partial Content) is COMMON and successful.
    # 2. Status 500 might occur if requesting out of bounds (sometimes).
    # 3. An empty list [] indicates end of results.

    if not resp.json():
        break

    start += step
```

## JSON Response Structure
The response is a **List of Product Objects**.

```json
[
  {
    "productId": "12345",
    "productName": "Whey Protein 900g",
    "brand": "IntegraMedica",
    "linkText": "whey-protein-900g-integral",
    "items": [
      {
        "itemId": "sku_1",
        "name": "Vanilla Flavor",
        "sellers": [
          {
            "sellerId": "1",
            "sellerDefault": true,
            "commertialOffer": {
              "Price": 129.90,
              "ListPrice": 159.90,
              "AvailableQuantity": 100
            }
          }
        ]
      }
    ]
  }
]
```

## Key Parsing Rules
1.  **Product ID**: `productId` (Root level).
2.  **SKUs**: `items` array. A product has multiple SKUs (Flavor/Size).
    *   *Strategy*: We typically pick the **First SKU** or the one with `sellerDefault: true`.
3.  **Price & Stock**: Located inside `items[].sellers[].commertialOffer`.
    *   `Price`: Current selling price.
    *   `AvailableQuantity`: Stock count.
4.  **Validation Rules**:
    *   Skip item when URL cannot be built from `linkText`.
    *   Skip item when `Price` is missing/invalid.
    *   If stock is unknown/unparseable, keep status as available (avoid false out-of-stock).
5.  **Context Persistence**:
    *   Save structured product payload in `ScrapedPage.raw_content` (`content_type="JSON"`).

## Implementation Examples
*   `scrapers/spiders/integral_medica.py`
*   `scrapers/spiders/dux.py`
*   `scrapers/spiders/max_titanium.py`
