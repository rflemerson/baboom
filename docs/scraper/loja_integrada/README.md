# Loja Integrada Data Extraction Strategy

This document details the technical findings regarding data extraction from **Loja Integrada** stores (specifically **Soldiers Nutrition**).

## Architecture Overview

Loja Integrada (AWSLI) uses a hybrid approach:
1.  **Server-Side Rendering (SSR)**: The primary HTML delivered to the browser contains the full product catalog for SEO and initial paint.
2.  **Frontend Logic**: Heavily relies on jQuery and embedded JSON objects for analytics (Google Tag Manager, Facebook Pixel).
3.  **Tracking API**: It uses a `setEvent` pixel to track user behavior, which carries a rich JSON payload.

## Data Sources

### 1. HTML DOM (Recommended)
The most robust way to extract data without authentication is parsing the DOM attributes. The theme renders critical data directly on the product cards.

*   **Product ID**: `div.listagem-item[data-id="..."]` (Internal Integer ID)
*   **Price**: `div.listagem-item[data-sell-price="..."]` (Float, e.g., "129.90")
*   **Availability**: Class `.indisponivel` or `.bandeira-indisponivel` exists on the card if OOS.

**Pros**: No auth required, standard across themes, fast (one request).
**Cons**: Limited metadata (missing precise SKU details or weight in listing).

### 2. Google Tag Manager / DataLayer
The site pushes clean JSON objects to `window.dataLayer` for analytics. This usually mirrors the internal product model.

**Pattern**:
```javascript
dataLayer.push({
  'ecommerce': {
    'detail': {
      'products': [{
        'name': 'Whey Protein...',
        'id': '76',
        'price': '125.90',
        ...
      }]
    }
  }
});
```

### 3. Browser-Side Objects (Verified)
Direct inspection of the `window` object revealed:
*   **`window.LIgtagDataLayer`**: Use this if running with a Headless Browser (Playwright/Selenium). It contains the rich data used for tracking.
    *   *Warning*: This object is NOT present in the static source. It is generated dynamically at runtime. Static parsers (BeautifulSoup) cannot see it.
*   **Price Placeholders**: In static HTML, prices appear as `R$ --PRODUTO_PRECO_DE--`.
    *   **Implication**: Static scraping **fails** to get the price. Browser rendering is **required**.
*   **Note**: `window.skuJson` and `window.product` are **NULL** on this store.

### 4. The `setEvent` Pixel
The user identified a POST request to `/_events/api/setEvent` (or `https://www.soldiersnutrition.com.br/_events/api/setEvent`).

**Payload**:
```json
{
  "event": {
    "type": "pageview",
    "name": "view_product",
    "data": {
       "item_id": "167256892",
       "price": 125.9,
       "quantity": 1
    }
  }
}
```

This request is **outgoing**. It sends data *from* the browser *to* the tracking server.
*   **Implication**: The browser *already possesses* this data before sending it.
*   **Source**: This data usually comes from the global `window.LI` object or the `dataLayer` mentioned above.

## API Access
*   **Public API**: There is no public JSON endpoint for product listing (e.g., `/products.json` is 404).
*   **Official API**: Requires `chave_api` and `chave_aplicacao` (Backend/ERP access). Not suitable for frontend scraping.
*   **SmartHint**: The search is powered by `smarthint.co`. It returns JSON but only for search results.

## Conclusion / Recommendation

**The "Static vs Dynamic" Verdict:**

1.  **Static Scraping (Requests/BS4)**: **INSUFFICIENT**.
    *   Can get Product ID and Name.
    *   **CANNOT** get Price (returns placeholders).

2.  **Browser Scraping (Playwright)**: **REQUIRED**.
    *   We created `docs/scraper/loja_integrada/inspect_strategy.py` as a robust dev tool / Proof of Concept.
    *   **Result**: Successfully extracts real prices (`R$ 199,90`, `R$ 125,90`) and the clean `window.LIgtagDataLayer` JSON.
    *   **Strategy**: Use Playwright to load the page, wait for `domcontentloaded`, and extract `window.LIgtagDataLayer`.
