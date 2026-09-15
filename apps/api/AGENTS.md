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
- Complete Shopify/VTEX unit lists reconcile absent variants; partial lists
  never delist. A price-less unit remains present but unavailable. Delisting
  and missing prices clear the current price without deleting price history.
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
- `ProductStore` is managed through the `ProductAdmin` inline, not as direct CRUD.
- The public REST API serves catalog browsing and alerts.
- `django_admin_rest_api` exposes the registered `ModelAdmin` classes as JSON at
  `/admin-api/`, under the same session auth and model permissions as the HTML
  admin. Authorization belongs to those permissions, not to the endpoint.
- See `docs/domain.md` for catalog and human curation boundaries.

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
