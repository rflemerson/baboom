# Scraping Strategies Overview

## Executive Summary
All target monitors use **API-First** strategies with structured endpoints for
catalog discovery, product listing, and variant-level details.
Each spider now persists two structured payloads in `ScrapedPage`:

- `api_context`: normalized product context collected from store APIs
- `html_structured_data`: structured metadata extracted from the product HTML
  with `extruct`

The agents pipeline currently consumes `api_context` from the backend GraphQL
field `sourcePageApiContext` and injects that payload into LLM prompts as
`[SCRAPER_CONTEXT]`.

All base spiders now follow the same Template Method hook contract for
category pagination:
`_initial_cursor()`, `_next_cursor(cursor, page_size)`,
`_fetch_page_items(category, cursor, page_size)`, and `_crawl_category(...)`.
This keeps store-specific logic isolated while the crawl orchestration remains
consistent across Shopify, VTEX GraphQL, VTEX Legacy, and Wap.Store.
The orchestration is centralized in `CatalogApiSpider`, which also provides
shared retry/backoff and crawl metrics logging (`categories_*`,
`products_collected`, `crawl_duration_ms`).

## Category Resolution Behavior

`CatalogApiSpider` now gives priority to an explicit `categories=[...]` override
when one is passed to the spider constructor. Dynamic discovery remains the
default for production crawls, but smoke tests and focused debugging sessions
can now constrain the crawl to a known subset safely.

If no explicit categories are provided, the spider falls back to dynamically
discovered categories first and then to `FALLBACK_CATEGORIES` when discovery
returns nothing.

## Technology Stack Breakdown

| Brand | Platform | Tech Stack | API Type | Authentication/Headers |
| :--- | :--- | :--- | :--- | :--- |
| **Growth Supplements** | Uappi (Wap.Store) | Custom/Vue.js | REST (Storefront) | `app-token: wapstore`<br>Browser-like headers<br>`verify=False` by default (Sucuri WAF) |
| **Black Skull** | VTEX IO | React/GraphQL | GraphQL (Persisted) | `extensions` param with Base64 encoded variables + Query Hash |
| **Integral Medica** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Max Titanium** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Probiotica** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Dux Nutrition** | VTEX Legacy | CMS/Legacy | REST (Search) | Standard HTTP (`_from`, `_to` pagination) |
| **Dark Lab** | Shopify | Liquid/Remix | REST (JSON) | `/collections/{handle}/products.json`, `/products/{handle}.js` |
| **Soldiers Nutrition** | Shopify | Liquid/Remix | REST (JSON) | `/collections/{handle}/products.json`, `/products/{handle}.js` |

---

## Detailed Strategies

### 1. VTEX Ecosystem
VTEX stores generally fall into two categories:
*   **VTEX IO (New)**: Uses GraphQL with "Persisted Queries". Requests are `GET` but require a complex `extensions` parameter containing the Query Hash and Base64 encoded variables.
    *   *Reference*: [VTEX GraphQL](./vtex_graphql.md)
*   **VTEX Legacy (Classic)**: Uses the `/api/catalog_system/pub/products/search` endpoint (or similar path proxies). Pagination is done via `_from` and `_to` query parameters.
    *   *Reference*: [VTEX Legacy](./vtex_legacy.md)

### 2. Uappi (Wap.Store)
This platform drives **Growth Supplements**. It exposes a robust public API meant for the frontend.
*   **Key Endpoint**: `/api/v2/front/url/product/listing/category`
*   **Quirks**: Strict Header requirements (`app-token`), SSL Verification issues (Sucuri WAF), and Rate/Limit caps (Max 30 items).
*   *Reference*: [Growth Strategy](./growth.md)

### 3. Shopify
**Dark Lab** and **Soldiers Nutrition** are Shopify stores.
*   **Key Endpoints**:
    * `/collections.json` (discover category handles)
    * `/collections/{handle}/products.json` (listing with pagination)
    * `/products/{handle}.js` (complete product context for variants/options/images)
*   **Strategy**: Iterate pages (`page=1`, `page=2`...) with `limit=250`.
*   **Structure**: JSON response contains `products` list with variations and prices clearly exposed.
*   *Reference*: [Shopify Strategy](./shopify.md)
