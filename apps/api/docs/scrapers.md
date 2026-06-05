# Scrapers

Scrapers are API-first. Each spider stores `ScrapedPage.api_context` from store APIs and `ScrapedPage.html_structured_data` from HTML extraction. `CatalogApiSpider` owns crawl orchestration, retry/backoff, and metrics.

## Growth

- Platform: Wap.Store REST.
- Base API: `https://www.gsuplementos.com.br/api/v2/front`
- Required header: `app-token: wapstore`
- Listing: `/url/product/listing/category?url=/proteina/&offset=0&limit=30`
- Pagination: `offset += 30`, `limit=30`
- `GROWTH_SSL_VERIFY` controls SSL verification; default is disabled for Sucuri compatibility.
- Product list usually lives under `conteudo.produtos`.

## Shopify

- Used by Dark Lab and Soldiers.
- Endpoints: `/collections.json`, `/collections/{handle}/products.json`, `/products/{handle}.js`
- Paginate with `page` and `limit=250`.
- Use detail JSON for variants, options, images, price, and availability.

## VTEX GraphQL

- Used by Black Skull.
- Endpoint: `/_v/segment/graphql/v1`
- Uses persisted queries through `extensions`.
- Variables are JSON-encoded, Base64-encoded, then embedded in `extensions`.
- Pagination uses `from` and `to`.
- Product list: `data.products.products`.

## VTEX Legacy

- Used by Integral Medica, Max Titanium, Probiotica, and Dux.
- Endpoint: `/api/catalog_system/pub/products/search`
- Pagination: `_from` and `_to`.
- HTTP 206 is a normal successful response.
- Empty list ends pagination.
- Price/stock: `items[].sellers[].commertialOffer`.

All scraper rows should be skipped when URL or price cannot be parsed.
