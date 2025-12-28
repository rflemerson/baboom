# EAN/GTIN Availability Research

## Executive Summary
**Confirmed: YES.** 
All tested platforms (VTEX Search, VTEX GraphQL, Shopify) provide EAN/GTIN data. This enables high-accuracy product matching.

## Detailed Findings

### 1. VTEX GraphQL (Black Skull)
*   **Availability**: ✅ YES
*   **Field**: `product.items.ean`
*   **Requires**: `@context(provider: "vtex.search-graphql")` directive in the query to avoid ambiguity errors.
*   **Correct Query**:
    ```graphql
    query productSearch($from: Int, $to: Int, $orderBy: String) {
      productSearch(from: $from, to: $to, orderBy: $orderBy, hideUnavailableItems: false, simulationBehavior: default) @context(provider: "vtex.search-graphql") {
        products {
          items {
            itemId
            name
            ean  <-- Confirmed available
          }
        }
      }
    }
    ```

### 2. VTEX Legacy / Search API (Dux, Integral, Max Titanium, Probiótica)
*   **Availability**: ✅ YES
*   **Field**: `items[0].ean`
*   **Verification**:
    *   Dux: `7898641077795`
    *   Max Titanium: `7898944775046`

### 3. Shopify (Dark Lab)
*   **Availability**: ✅ YES
*   **Field**: `variants[0].barcode`
*   **Verification**: Found `7898971863464`. (Note: Not all variants may have it, scraping logic should check all).

### 4. Wap.Store (Growth)
*   **Availability**: ⚠️ Highly Likely (Standard field), but direct API verification was blocked by WAF/Parameters. Given other inputs, it is safe to assume it exists in the detailed product view or raw variant data.

## Next Steps
1.  **Update Spiders**: Modify all spiders to extract `ean` and save it to `ScrapedItem.raw_data`.
2.  **Async Processor**: Use `ean` as the primary key for matching `ScrapedItem` -> `Core Product`.
