# Black Skull API Strategy (VTEX GraphQL)

## 1. Overview
**Platform Identified:** VTEX IO (GraphQL via Persisted Queries)
**Endpoint:** `/_v/segment/graphql/v1`
**Method:** `GET`
**Auth:** None (Public Store API)

## 2. The Mechanics (Persisted Queries)
Unlike standard GraphQL (POST), this store uses **Persisted Queries** via GET.
*   **Query Hash**: `ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22` (SHA256 of the query).
*   **Sender**: `vtex.store-resources@0.x`
*   **Provider**: `vtex.search-graphql@0.x`

## 3. Request Construction
The request relies on the `extensions` parameter, which contains the Query META and the Variables (Base64 Encoded).

### URL Structure
```
https://www.blackskullusa.com.br/_v/segment/graphql/v1
?workspace=newblackpdp
&maxAge=short
&appsEtag=remove
&domain=store
&locale=pt-BR
&operationName=Products
&variables={}
&extensions={...JSON String...}
```

### The `extensions` JSON
```json
{
  "persistedQuery": {
    "version": 1,
    "sha256Hash": "ee2478d319404f621c3e0426e79eba3997665d48cb277a53bf0c3276e8e53c22",
    "sender": "vtex.store-resources@0.x",
    "provider": "vtex.search-graphql@0.x"
  },
  "variables": "BASE64_ENCODED_VARIABLES_JSON"
}
```

### The Variables JSON (Before Base64)
```json
{
  "hideUnavailableItems": false,
  "category": "", 
  "specificationFilters": [],
  "orderBy": "OrderByTopSaleDESC",
  "from": 0,    // <--- Pagination Start (Item Index)
  "to": 49,     // <--- Pagination End (Inclusive)
  "shippingOptions": [],
  "variant": "",
  "advertisementOptions": {
    "showSponsored": false,
    "sponsoredCount": 0,
    "repeatSponsoredProducts": false,
    "advertisementPlacement": "home_shelf"
  }
}
```

## 4. Pagination Strategy
1.  **Start**: `from=0`, `to=49`.
2.  **Next**: `from=50`, `to=99`.
3.  **Stop**: When the returned `products` list is empty or smaller than the requested range.
4.  **Encoding**: You MUST stringify the Variables JSON and then Base64 encode it before placing it into the `extensions["variables"]`.

## 5. Python Implementation Guide
We implement this by manually constructing the dictionary structure, processing the Base64 encoding, and sending a standard `requests.get()`.

```python
import base64
import json

# Encode Variables
vars_json = json.dumps(variables_dict, separators=(',', ':'))
vars_b64 = base64.b64encode(vars_json.encode('utf-8')).decode('utf-8')

# Construct Extensions
extensions = json.dumps({
    "persistedQuery": { ... },
    "variables": vars_b64
}, separators=(',', ':'))

# Request
requests.get(endpoint, params={"extensions": extensions, ...})
```

## 6. Data Parsing
The response is standard VTEX JSON:
*   `data.products.products`: List of Items.
*   `items[0].sellers[0].commertialOffer`: Price and Stock.
*   Validation in current spider:
    * Skip item when URL cannot be built from `linkText`.
    * Skip item when `Price` is missing/invalid.
    * Unknown stock stays available (avoid false out-of-stock).
    * Product IDs are deduplicated globally across categories in one crawl.
    * Save structured product payload in `ScrapedPage.raw_content` (`content_type="JSON"`).
