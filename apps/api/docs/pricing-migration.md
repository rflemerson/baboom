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
| 6 | Cart and checkout groups, `ShippingQuote`, `TaxFeeQuote`, `CurrencyConversionQuote`, `PricingQuote` | Done for single-checkout purchases. Quotes replay from their snapshot alone (`pricing.replay`), with codes and postal codes as keyed tokens; stored shipping and tax quotes reach the engine; taxes are unknown unless the market's prices include them or a source was consulted. **Pending:** no adapter writes `ShippingQuote` or `TaxFeeQuote` yet (the VTEX cart simulation is a pilot, not enabled), and order-level terms across several checkout groups are reported `unsupported` instead of evaluated per group |
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

Each step is reversible until the last one. Nothing here deletes a fact.

1. **Deploy** the code. Migrations only add tables and columns; old workers
   keep working against them.
2. **Identity:** `manage.py backfill_commercial_identity`, read the preview
   (offers without a seller are listed for review), then run it with
   `--apply`.
3. **History:** `manage.py backfill_legacy_price_observations`, then with
   `--apply`. Legacy prices become `legacy_unknown`, nothing more.
4. **Projections:** `manage.py shell -c "from pricing.tasks import
   refresh_projections; print(refresh_projections())"`, or wait for the next
   crawl or the hourly refresh.
5. **Shadow:** `manage.py compare_pricing_shadow --policy listed --country BR
   --currency BRL`. With no
   promotion published, both sources must agree; every difference is read,
   explained and fixed at its cause. `--strict` turns any difference into a
   failure, for a gate.
6. **Scenarios first:** `?scenario=cash` is live from step 4 without changing
   the default ranking; check it against the stores' own pages.
7. **Switch:** add the country to `PRICING_PROJECTION_COUNTRIES` (e.g.
   `BR`). Rollback is removing it
   back to false: legacy prices are still written by every crawl.
8. **Later, once production has run on projections without regressions:**
   stop writing `PriceObservation`, then remove `Offer.current_price` and the
   legacy selector in their own migrations.

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
