# API Guide

## Scope

- Django API, admin, public REST catalog, and scraping integration.
- Public frontend lives in `apps/web`; do not add Django template frontend flows here.

## Commands

```bash
pip install -e .[dev]
prek run --all-files
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/coverage run manage.py test && .venv/bin/coverage report
.venv/bin/python manage.py runserver
```

## Testing

Tests mirror the production modules under each app's `tests/` package:

- model invariants live in `core/tests/models/`;
- selectors and business services live in `core/tests/selectors/` and
  `core/tests/services/`;
- admin, API, and management-command tests live in `core/tests/admin/`,
  `core/tests/apis/`, and `core/tests/commands/`;
- scraper normalizers, crawler infrastructure, platform spiders, scraper
  services, tasks, and commands live in the corresponding directories under
  `scrapers/tests/`;
- MCP loader, RPC, and endpoint tests live in `mcp_server/tests/`;
- OAuth tests live beside the OAuth modules in `baboom/oauth/tests/`.

Run the Django test runner from this directory with the local-only key:

```bash
DJANGO_SECRET_KEY=test-only-local .venv/bin/python manage.py test
DJANGO_SECRET_KEY=test-only-local .venv/bin/python manage.py test --shuffle
DJANGO_SECRET_KEY=test-only-local .venv/bin/python manage.py test --reverse
# Real store verification is manual and may access the network:
.venv/bin/python manage.py verify_scraper_stores [SPIDER ...]
```

Coverage uses the configured branch measurement:

```bash
DJANGO_SECRET_KEY=test-only-local .venv/bin/coverage run manage.py test
.venv/bin/coverage report -m
```

The configured `baboom.test_runner.NoNetworkTestRunner` blocks Python socket
connections outside loopback and the test-database hosts, and blocks native
`curl_cffi` transfers. All crawler tests use in-memory Scrapy responses and
never collect from the network. Real store verification was moved out of the
suite; run `verify_scraper_stores` manually when network access is intentional.
That command uses the same public `run_spider_monitor` workflow as Celery: it
persists scraped items and offers, creates a `ScraperRun`, and reconciles
offers that a successful crawl no longer sees.

## Architecture

- Business workflows: `core/services/` and `scrapers/services.py`.
- DTOs: `core/dtos.py`; scraper handoff contracts live in `scrapers/contracts.py`.
- Scraper normalizers live in `scrapers/normalizers/`. They are pure payload
  transformations and must not import Django database models or persistence
  services. Scrapy platform spiders live in `scrapers/crawler/spiders/`, emit
  `ScrapedProductInput`, and `scrapers/crawler/pipelines.py` hands those items
  to `ScraperService.save_product_snapshot`.
- Celery launches one `scrapy crawl <spider>` subprocess per monitor and uses
  the dumped Scrapy statistics to close `ScraperRun`; the task preserves the
  empty-after-history failure rule and terminates crawls over 30 minutes.
- Each normalized page states its coverage per dimension (`CoverageInput`):
  only a page whose `offers` were read completely reconciles absent units;
  partial pages never delist. A price-less unit remains present but
  unavailable; an unread stock is `unknown`, never available.
- Every price a source states travels as a `PriceInput` (role, payment scope
  and method, installments, what it already includes) and is appended by
  `offers.observations.ObservationService` as an `OfferPriceObservation` only
  when its condition's amount changes. Prices are exact decimals from parse to
  row. Delisting
  and missing prices clear the current price without deleting price history.
- Commercial identity: `commerce` (channel, market, seller account, merchant,
  fulfillment, payment method, programme) imports only `common`; `offers`
  imports only `common` and `commerce`. A spider declares its market
  (`CatalogSpider.MARKET_*`), each normalizer names the seller
  (`SellerInput`), and ingestion places every offer under its listing, variant
  and seller account (`OfferIdentityService`). A known seller is never
  overwritten. `baboom/tests/test_import_boundaries.py` enforces the imports.
- Promotions (`promotions`): a `Promotion` has versioned `PromotionRevision`s
  that own their codes, scopes, effects, reward terms and compatibility rules.
  Setting a draft's status to informative or executable publishes it through
  `PromotionService` (validated, hashed, frozen); a published revision changes
  only status, guarded in the models and, on PostgreSQL, by triggers. Edits
  start a new revision (admin action). The MCP skill `promotion-curation`
  explains the workflow to agents.
- The pricing engine (`pricing/domain/`) is pure: frozen dataclasses in,
  `PricingResult` out, `now` passed in, no Django, database, network or
  clock. `evaluate(Inputs)` selects a base price per line for the policy's
  scenario (listed, cash, payment), keeps the executable revisions the
  scenario counts, applies every compatible combination stage by stage and
  returns the cheapest, with a decision for every candidate. Unknown is never
  zero; rewards never lower what is paid.
- `pricing.services.PricingService` is the only bridge between the ORM and the
  engine: `FactLoader` reads offers, the standing observation of each price
  condition (a complete read withdraws what it no longer states), and the
  revision in force of each promotion; `quote()` keeps a `PricingQuote` whose
  snapshot reproduces the result, with buyer codes and postal codes hashed.
  Policies (`PricingPolicyRevision`) are frozen once published; `listed` and
  `cash` v1 are seeded.
- Ranking reads `OfferScenarioProjection` rows (one per linked offer and
  published public policy) through `pricing.selectors.projected_prices`, passed
  to `core.selectors.public_catalog_products` as its price source; expiry is
  checked at read time. Each offer keeps the winner (`best`), the best price per
  exact set of coupon and cashback, and `base` (no promotion); the default read
  takes the cheapest still valid, so an ended promotion falls back to a price
  without waiting for the worker. `?scenario=<policy key>` picks the policy (default:
  the `is_default` one); every request ranks one market (`?country=`,
  `?currency=`, default BR/BRL). Until `PRICING_PROJECTION_COUNTRIES` names a market (temporary
  launch switch), its catalog reads `core.selectors.current_prices` instead.
  Public policies: `normal` (store price, no benefits, default) and `best`
  (best price paid now; falls back to normal).
- `pricing.invalidation.Repricing` decides what a change reaches: it first
  expires rows the change may have made wrong (a moved route's old and new
  offers; prices a changed promotion gave), then gathers the offers of one
  transaction into a single `refresh_projections` after commit. `pre_save`
  receivers keep the replaced row so its old targets are repriced too.
  Category moves through treebeard's `move()` skip `save()` and wait for the
  hourly refresh. Crawls and promotions announce
  themselves with their own signals (`offers_observed`, `revision_changed`;
  a promotion reprices only the offers its target scopes name). Admin-edited
  rows of other apps (`ProductStore`, `Product`, `PurchaseRoute`) use model
  signals in `pricing/receivers.py`; pricing's own writes (policy admin) call
  `Repricing` directly. An hourly beat entry refreshes everything.
- Services are classes; a module-level function is a selector, a task or a
  signal receiver. Helpers live as methods of the class that uses them.
- The engine also receives purchase routes (a tracked cashback needs an
  activation route per line), quoted shipping and taxes (`fees_status`:
  included in prices, consulted, or not consulted, which is unknown), and
  refuses order-level terms across several checkout groups as unsupported.
  `pricing.replay.QuoteReplay` re-evaluates a kept quote from its snapshot
  alone; `check()` compares the whole canonical result and tells apart
  "differs", "other engine version" and "invalid snapshot" (quote admin
  action "Replay from the snapshot").
- Policies are published only through `pricing.policies.PolicyService`
  (admin action "Publish and project"): `PricingPolicyRevision.clean`
  refuses unknown rule keys and wrongly typed values (`models.RULES`).
- `backfill_commercial_identity` previews, and with `--apply` writes, the
  identity of offers captured before it existed; sellers come only from the
  captured context, and the rest are listed for review.
- `scrapers/management/commands/cutover_offer_identities.py` is an explicit,
  preview-first legacy-identity transition. It never runs on deployment;
  operators must review ambiguous mappings before opting into archival.
- Public catalog and alerts: REST.
- Scrapers retain `ScrapedPage` metadata and the store's own product context;
  humans curate the catalog through Django admin.
- Nothing here fetches or stores product-page HTML. Reading a product page is
  the curator's job, done live, with a browser.
- Query composition belongs in `selectors.py`.
- Product, nutrition, component, flavor, brand, store, tag, category and alert
  subscriber management is manager-facing through Django admin.
- A product is one package with one nutrition table (at most one
  `ProductNutrition`). `ProductStore` links a product to one captured `Offer`,
  through its own `ProductStoreAdmin`. The store is resolved from the offer's
  `store_slug` via `Store.scraper_slug`, never chosen, and `ProductStore.clean()`
  refuses an offer whose stated flavor (`Offer.flavors`) the product's table does
  not list; a product without a table yet takes the offer. Curation never types
  a price, URL or offer id.
- The public REST API serves catalog browsing and alerts.
- `django_admin_rest_api` exposes the registered `ModelAdmin` classes as JSON at
  `/admin-api/`, under the same session auth and model permissions as the HTML
  admin. Authorization belongs to those permissions, not to the endpoint.
- See `docs/domain.md` for catalog and human curation boundaries, and
  `docs/pricing.md` for the pricing domain: its decisions, model and migration.

## Patterns

- Use explicit service classes for orchestration.
- Keep models focused on persistence and invariants.
- Prefer typed DTOs over untyped dictionaries.
- Keep public functions typed; move annotation-only imports into `TYPE_CHECKING`.
- Use `ClassVar[...]` for mutable admin metadata.
- Avoid `Any`, `# noqa`, `type: ignore`, and broad lint bypasses.
- Prefer plain `assert` in tests.

## Quality

- Run `prek run --all-files` for substantial changes and review hook edits.
- Do not commit secrets or Django `SECRET_KEY` values.
- Keep production host, TLS and cookie settings explicit.

## Pricing second-review changes

- Load/translate facts in `pricing/facts.py`, cost versions in `pricing/costs.py`,
  and shared quote/projection inputs in `pricing/context.py`.
- What a promotion may declare (`EFFECT_SPECS`, condition traversal) lives in
  pure `promotions.rules`; it is the only app module `pricing/domain` may
  import, and it imports nothing. Promotions never import pricing.
- Scraper price restrictions are closed/validated and survive observation
  persistence. Non-unit amounts/restricted contexts remain explicit limitations.
- Projections persist the selected route URL/ID and comparison objective;
  `core` price sources provide both `amount` and `comparison_amount`, plus
  `pricing_details`. Keep displayed checkout amounts separate from ranking.
- Unreleased migrations are squashed: new apps start at `0001`. Rebuild
  projections with `rebuild_pricing_projections` (preview) and `--apply` only
  in an authorized environment.
- See `docs/pricing-audit.md` for outstanding second-review requirements. These
  are internal work, not missing connector credentials.
