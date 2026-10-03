# Scrapers

Scrapers are API-first and run as Scrapy subprocesses. Scrapy owns request
scheduling, concurrency, retries, throttling, duplicate URLs, and statistics;
the custom downloader middleware retains TLS impersonation rotation, WAF
detection, and `Retry-After`; a 429 without that header waits 30 s, then
twice as long on each retry, because Shopify throttles by IP and answers
without one. The platform spiders only discover and paginate
their endpoints, while pure normalizers under `scrapers/normalizers/` map
payloads to one source page and its independently buyable, priced offers.
`CatalogPipeline` is the only handoff to `ScraperService.save_product_snapshot`;
no spider fetches or stores product-page HTML.

## Growth

- Platform: Wap.Store REST.
- Base API: `https://www.gsuplementos.com.br/api/v2/front`
- Required header: `app-token: wapstore`
- Listing: `/url/product/listing/category?url=/proteina/&offset=0&limit=30`
- Pagination: `offset += 30`, `limit=30`
- `GROWTH_SSL_VERIFY` controls SSL verification; default is disabled for Sucuri compatibility.
- Product list usually lives under `conteudo.produtos`.
- `atributos.simples` lists the buyable units inside one page, each with its
  own `sku`, `precos` and `estoque` (the 19 flavors of the 1 kg whey, the 400 g
  and 800 g of Daily Whey): one offer each, keyed `<id>-<idAtributoValor>`.
  `atributos.unico` lists sibling pages, one product id per value, and names
  the value the page itself is. A page without `simples` is one offer, `<id>`.
- The page URL does not change with the chosen unit, so selection is a
  `form_option` naming the attribute and value to pick.

## Shopify

- Used by Dark Lab, Soldiers, and Integralmedica.
- Endpoints: `/collections.json`, `/collections/{handle}/products.json`, `/products/{handle}.js`
- Paginate with `page` and `limit=250`.
- Use detail JSON for variants, options, images, price, and availability.

## Nuvemshop

- Used by Dux Nutrition.
- No public catalog JSON API is used. Listing pages name products through
  JSON-LD, which describes only the first unit of each.
- Each listed product's page is read for `LS.variants`: one offer per visible
  variant, keyed by its sku, reachable with `?variant=<id>` (verified to open
  the page on that unit). Option names come from the `variation_N` labels of
  the `#product_form`.
- A product page that cannot be read marks the crawl incomplete and falls back
  to the listing's single unit, so its price does not freeze.

## VTEX GraphQL

- Used by stores configured with `VtexGraphqlSpider`.
- Endpoint: `/_v/segment/graphql/v1`
- Uses persisted queries through `extensions`.
- Variables are JSON-encoded, Base64-encoded, then embedded in `extensions`.
- Pagination uses `from` and `to`.
- Product list: `data.products.products`.

## VTEX Legacy

- Used by Black Skull, Max Titanium, and Probiotica.
- Endpoint: `/api/catalog_system/pub/products/search`
- Pagination: `_from` and `_to`.
- HTTP 206 is a normal successful response.
- Empty list ends pagination.
- Price/stock: `items[].sellers[].commertialOffer`.

All scraper rows should be skipped when URL or price cannot be parsed.
