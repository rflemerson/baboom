# Pricing connectors

How a store or marketplace reaches the pricing domain, what each adapter
reads, and what is still blocked on access. Rules in
[pricing-model.md](./pricing-model.md#adapters).

## Adapters

Each normalizer declares `capabilities` (`scrapers/capabilities.py`); tests
refuse a registered spider without them. Per-provider limits in
`PROVIDER_LIMITS` apply to every spider of a platform.

| Adapter | Version | Variants | Sellers | Payment prices | Cart quote | Route | Stores |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VTEX search/GraphQL | 2 | complete | named, every seller | complete (`Installments`) | none | variant | Black Skull, Max Titanium, Probiótica |
| Shopify | 2 | complete | store only | none | none | variant | Dark Lab, Integralmédica, Soldiers |
| Wap.Store | 2 | complete | store only | partial (cash and plan, method unnamed) | none | page only | Growth |
| Nuvemshop | 2 | complete | store only | partial (payment price unnamed, plans per gateway) | none | variant | DUX |
| Feed | 1 | complete | named | as the feed states | none | variant and seller | none yet |

"Complete" is what the adapter can read when the source exposes it; each page
still states its own coverage, and a 403, 429 or parse failure marks the
dimension failed, never absent.

## Onboarding a store or marketplace

1. **Same platform.** Subclass the platform spider with `name`, `STORE_SLUG`,
   `BRAND_NAME`, `BASE_URL` and the market (`CHANNEL_KIND`,
   `MARKET_COUNTRY`, `MARKET_CURRENCY`, `MARKET_TIMEZONE`). No other code.
2. **Structured feed.** Subclass `FeedSpider` with the same settings and
   `FEED_URL`. The feed format (`scrapers/normalizers/feed.py`) names
   listings, variants, sellers, featured offers, stock and typed prices, so a
   marketplace with many sellers needs no new code.
3. **New protocol.** A new normalizer with fixtures, its capabilities and its
   provider limits. A new commercial mechanic is a new evaluator in
   `pricing/domain/effects.py`, never a branch on a store.
4. **Before enabling:** record the source, its authorization, its key scheme
   (`OfferSourceIdentity.scheme`), its rate limits and a fixture per payload
   shape; add a beat entry spaced from the platform's other stores; run
   `verify_scraper_stores <spider>` once by hand.
5. **After the first crawl:** link offers to products (admin or MCP), and run
   `refresh_projections` or wait for the hourly refresh.

## Marketplaces: blocked on access

Nothing here claims coverage of a real marketplace. The synthetic feed tests
(`scrapers/tests/test_feed_generality.py`) prove the model; real integration
needs access the project does not have yet.

| Marketplace | What the model already supports | What is missing |
| --- | --- | --- |
| Amazon | Market per site; seller, condition and fulfillment in the offer identity; featured offer as an observation; ASIN as `Listing.catalog_product_id` | Selling Partner API access: a registered developer application and authorization from an account entitled to the pricing endpoints. Without it, no adapter is written against guessed payloads |
| Mercado Livre | Market per site; seller accounts by id; item and variation as listing and variant; catalog product id kept apart from the item | A registered application and an access token, and a check of which search and item endpoints that token may read |

When access exists, each becomes a normalizer (or a feed produced from the
official API) with real fixtures; the engine, promotions and ranking stay
unchanged. URLs that select a seller are used only where the connector shows
the mechanism works; otherwise a route reports `fixes_seller=False`.

## Restriction handoff

A synthetic adapter may emit `PriceInput` with `quantity_min`, `quantity_max`,
`amount_basis`, `currency`, capture/evidence stage, included adjustments and
`context` containing program/destination/subscription restrictions. Unknown
keys are rejected. Restricted order/line values remain historical observations,
with unsupported/unknown pricing decisions until a matching calculation exists.
Shipping source guarantees require `external_quote_id` and
`execution_guaranteed`; a future expiration alone is not a booking guarantee.
