# Pricing migration

How the model in [pricing-model.md](./pricing-model.md) is built, delivery by
delivery, and how today's data moves into it without losing a fact. Each
delivery ships code, tests, migrations and the docs it changes, and reports
what works, what was tested and what is still pending.

## Deliveries

| # | Builds | Done when |
| --- | --- | --- |
| 0 | Audit corrections, executable fixtures, purchasable allowlist, deploy pinned to a CI-passed SHA | Done: `3e17bf4`, `34098e4`, `fb97f44` |
| 1 | This model, its decisions and this plan | Reviewed before any migration |
| 2 | `commerce` (currency, channel, market, seller account, merchant binding, fulfillment, payment method, provider, program); `Listing`, `ListingVariant`, `OfferSourceIdentity`, `FeaturedOfferObservation`; offer identity fields; store bindings | Done. Two sellers and two markets of one listing coexist without collision; every existing offer, link and price history kept; run `backfill_commercial_identity` (preview, then `--apply`) after deploying |
| 3 | `ObservationBatch`, `CollectionCoverage`, `Evidence`, `OfferPriceObservation`, `AvailabilityObservation`; the scraper contract carries several prices, Decimal from parse to row; VTEX keeps every seller; coverage replaces `complete_unit_list` | Done. The audit fixtures produce typed observations; a cash price records the discount it includes; 403/429 never delist; run `backfill_legacy_price_observations` after the identity backfill |
| 4 | `promotions` with immutable revisions, scopes, conditions, effects, reward terms, compatibility, codes, evidence and routes; `PromotionService` for admin and MCP | Done. PRIMEIRACOMPRA is registered and published through the admin JSON API (the MCP surface); a published revision is frozen in the models and by PostgreSQL triggers; a new revision leaves the old hash intact |
| 5 | `pricing.domain`: every mechanic listed in the model, the condition tree, stages and precedence, allocation, rewards | Done. `pricing/tests/domain/test_engine.py` runs the matrix offline, including the research's full example (R$ 114.60, net R$ 109.47) |
| 6 | Cart and checkout groups, `ShippingQuote`, `TaxFeeQuote`, `PricingQuote` | Done for single-checkout purchases. Quotes replay from their snapshot alone (`pricing.replay`), with codes and postal codes as keyed tokens; stored shipping and tax quotes reach the engine; taxes are unknown unless the market's prices include them or a source was consulted. **Pending:** no adapter writes `ShippingQuote` or `TaxFeeQuote` yet (the VTEX cart simulation is a pilot, not enabled), and order-level terms across several checkout groups are reported `unsupported` instead of evaluated per group |
| 7 | `PricingPolicyRevision`, `OfferScenarioProjection`, invalidation, REST, Vue | Done. Projections per offer, policy and market; ranking and pagination in the database, one country and currency per request; `?scenario=cash` in the API and a "Price shown" selector in Vue; caches bounded by the earliest expiry; the link limitation of third-party sellers shown; the default stays legacy per country until listed in `PRICING_PROJECTION_COUNTRIES` |
| 8 | Current adapters on the new contract; Amazon and Mercado Livre per authorized access; onboarding procedure; quota-aware scheduling | Done for what access allows: capabilities per adapter, provider limits, a configuration-only feed adapter proven by synthetic marketplace tests, and the onboarding procedure. Amazon and Mercado Livre wait for authorized access (see connectors) |
| 9 | Shadow run, comparison, activation per market and policy, rollback, removal of compatibility fields | Code done: `compare_pricing_shadow` per market (amount, offer, seller, variant, link), the per-country switch and the runbook below. Activation and the removal of compatibility fields wait for a production shadow run |

## Moving today's data

Counts come from the database at migration time, never from a conversation.

1. **Inventory.** A preview command reports every `Store`, `Offer`,
   `ProductStore`, `PriceObservation`, `ScrapedPage` and `ScrapedItem`, with the
   invariants each migration step relies on, and stops on a violation.
2. **Identities in parallel.** Per `Store` with a `scraper_slug`: one channel
   (`independent_store`, its platform as adapter), one market (BR, BRL,
   America/Sao_Paulo, with provenance "source contract", not "observed"), one
   seller account marked `is_channel_owner`. `Store.seller_account` is set.
3. **Offers keep their primary keys.** Each offer gets a listing (from its
   `ScrapedPage`), a listing variant (from its options and selection), and an
   `OfferSourceIdentity` with scheme `legacy` holding `store_slug` and
   `external_id`. `ProductStore` rows do not move.
4. **Sellers are not guessed.** An offer gets the store's own seller account
   only where the source names it: VTEX `sellerId` "1" in the stored context,
   or a platform without third-party sellers. Anything else is `unresolved`,
   listed for review. Historic observations keep no seller.
5. **Splitting is previewed.** If one legacy offer turns out to be several
   sellers, the split is a preview listing ambiguities; nutrition and links are
   never redistributed automatically.
6. **History.** Each `PriceObservation` becomes an `OfferPriceObservation`
   with `semantics=legacy_unknown`, role `payable`, stage `catalog`, no payment
   method and composition `unknown`. No Pix, installment, code or composition
   is back-filled.
7. **Double write.** One normalized ingestion writes the new observation, the
   legacy row and the compatibility projection in one transaction, idempotent
   on `(batch, subject, condition_key)`.
8. **Shadow comparison.** The new engine runs beside the selector, per market
   and policy, recording differences in price, seller, variant, link and
   active denominator. Differences are investigated, never forced equal.
9. **Cutover.** Reading switches per market and policy, with a read rollback.
   Expansion migrations keep old workers working during a deploy; fields are
   removed only in a later delivery. History is corrected by new records,
   never rewritten.

`Offer.current_price` keeps its meaning only with a known market, currency and
policy; before a second currency exists it is replaced by a projection.

## Gaps closed

Delivery 3 closed the gaps the audit found: prices parse to exact decimals
(also `R$ 1.234,56`, read before as 1.234); an unread stock is `unknown`,
never available; every VTEX seller is its own offer, its default seller a
`FeaturedOfferObservation`; the contract carries every price with its meaning;
and per-dimension coverage replaced the single `complete_unit_list` flag.

## Cutover runbook

Production runs `767150b`, before every pricing app. The deploy changes no
price a buyer sees: a market reads projections only once
`PRICING_PROJECTION_COUNTRIES` names it; until then the catalog shows each
offer's last read price (`core.selectors.current_prices`).

1. **Deploy.** Migrations create `commerce`, `promotions` and `pricing`, add
   identity columns to `offers`, `core` and `scrapers`, seed the reference
   data and the `normal` and `best` policies, and install the freeze
   triggers. Check `CATALOG_PRODUCTS_EDGE_CACHE_SECONDS` in the environment:
   it caps how long the CDN keeps a page of prices (default 600).
2. **Identity:** `manage.py backfill_commercial_identity`, read the preview,
   then `--apply`.
3. **History:** `manage.py backfill_legacy_price_observations`, then
   `--apply`. Legacy prices become `legacy_unknown` and keep their age,
   except the newest copy of a listed offer whose `current_price` it states:
   the last crawl read that price, so it is confirmed at `last_seen_at`.
4. **Projections:** `manage.py rebuild_pricing_projections --apply`.
5. **Coverage:** `manage.py pricing_coverage --country BR --currency BRL
   --details` lists, per policy, products priced today that projections
   leave without a price, by store and reason (stale, unavailable, no
   projection) for the offer that wins today's price, and where the winning
   offer or link differs from the `normal` projection's. `--fail-on-loss` exits
   with an error while any product loses its price. Wait for full crawls of
   the stores it names and repeat.
6. **Switch:** add the country to `PRICING_PROJECTION_COUNTRIES`. Rollback is
   removing it.
7. **After every market is switched and stable:** remove the setting and
   `current_prices`, then the legacy writes (`Offer.current_price`,
   `PriceObservation`) once ingestion updates offers and stock without them.
   The two backfills go after the recovery period;
   `rebuild_pricing_projections` and `pricing_coverage` stay as operational
   tools.

## External review, 2026-10-04

An external review of `767150b..5038a46` found fourteen defects (R01-R14)
where a guarantee did not cross every layer. All are fixed, each with the
reviewer's reproduction in `pricing/tests/test_review_regressions.py` and
acceptance tests beside the code it concerns:

| Finding | Fixed by |
| --- | --- |
| R01 withdrawn price reappearing; R02 backfill refreshing old prices; R03 seller collision moving facts; R14 VTEX unknown stock read as available | `03d9c5d` |
| R04 observation restrictions lost; R05 currencies compared nominally; R13 caches outliving prices | `b1d7fcf` |
| R06 tracked cashback without a route; R07 Pix applied twice in mixed carts; R09 multibuy ignoring its cap; R12 `any` payment unused | `3a2bd32` |
| R08 snapshots that could not replay; R10 exponential combination search; R11 priceless quotes raising | `655e1f0` |

### Activation gate, verified 2026-10-04

- Backend suite on SQLite and PostgreSQL (572 tests; the freeze triggers run
  on PostgreSQL), including the review's reproductions and
  `pricing/tests/test_migration_path.py`: legacy history and a third-party
  VTEX seller through both backfills, a new crawl that collides, projections
  and the shadow gate.
- A local copy of production (523 published products), migrated and
  backfilled: `compare_pricing_shadow --policy listed --country BR
  --currency BRL` reports 523 equal, comparing amount, offer, seller,
  variant and link.
- Vue unit tests, and Playwright E2E including `e2e/scenario.spec.ts`
  (choosing "Paid at once" requests `scenario=cash` and shows the method,
  the currency and the seller warning). CI does not run E2E; run them
  locally with `npx playwright test`.

## Migrations

Nothing below is applied in production, so each new app starts at `0001`:

| App | Migrations |
| --- | --- |
| commerce | `0001_initial`, `0002_seed_reference_data` |
| offers | `0005_commercial_identity` |
| core | `0010_store_seller_account` |
| scrapers | `0004_scrapedpage_listing` |
| promotions | `0001_initial`, `0002_freeze_published_revisions` (PostgreSQL trigger) |
| pricing | `0001_initial`, `0002_default_policies`, `0003_hourly_projection_refresh`, `0004_freeze_published_policies` (PostgreSQL trigger) |

Verified on 2026-10-04 against a local restore of the production dump:
`migrate`, both backfills and `rebuild_pricing_projections --apply` (644
linked offers, 1288 projections, 523 products in the catalog).

`rebuild_pricing_projections` is repeatable. It locks offer rows, preserves
projections computed at a later requested moment and never changes price
history or published rules. Engine 1.1.0 snapshots require schema version 1
and that exact engine version for replay.
