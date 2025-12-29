# Scraping Strategies Overview

## Executive Summary
All 8 target monitors have been migrated from "Hybrid/Playwright" to **API-First** strategies. This provides 10x-100x performance improvements, reduced resource consumption, and greater stability.

## Technology Stack Breakdown

| Brand | Platform | Tech Stack | API Type | Authentication/Headers |
| :--- | :--- | :--- | :--- | :--- |
| **Growth Supplements** | Uappi (Wap.Store) | Custom/Vue.js | REST (Storefront) | `app-token: wapstore`<br>`User-Agent: insomnia/12.2.0`<br>`verify=False` (Sucuri WAF) |
| **Black Skull** | VTEX IO | React/GraphQL | GraphQL (Persisted) | `extensions` param with Base64 encoded variables + Query Hash |
| **Integral Medica** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Max Titanium** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Probiótica** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Dux Nutrition** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Dark Lab** | Shopify | Liquid/Remix | REST (JSON) | `/products.json?limit=250&page=1` |

---

## Detailed Strategies

### 1. VTEX Ecosystem
VTEX stores generally fall into two categories:
*   **VTEX IO (New)**: Uses GraphQL with "Persisted Queries". Requests are `GET` but require a complex `extensions` parameter containing the Query Hash and Base64 encoded variables.
    *   *Reference*: [Black Skull Strategy](blackskull_api_strategy.md)
*   **VTEX Legacy (Classic)**: Uses the `/api/catalog_system/pub/products/search` endpoint (or similar path proxies). Pagination is done via `_from` and `_to` query parameters.
    *   *Reference*: [VTEX Search Strategy](api_strategy_vtex.md)

### 2. Uappi (Wap.Store)
This platform drives **Growth Supplements**. It exposes a robust public API meant for the frontend.
*   **Key Endpoint**: `/api/v2/front/url/product/listing/category`
*   **Quirks**: Strict Header requirements (`app-token`), SSL Verification issues (Sucuri WAF), and Rate/Limit caps (Max 30 items).
*   *Reference*: [Growth Strategy](growth_api_strategy.md)

### 3. Shopify
**Dark Lab** is a standard Shopify store.
*   **Key Endpoint**: `/products.json`
*   **Strategy**: Iterate pages (`page=1`, `page=2`...) with max limit (`limit=250`).
*   **Structure**: JSON response contains `products` list with variations and prices clearly exposed.
*   *Reference*: [Shopify Strategy](api_strategy_shopify.md)
