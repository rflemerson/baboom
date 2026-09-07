# API Guide

## Scope

- Django API, admin, REST catalog, authenticated scraper GraphQL, and scraping integration.
- Public frontend lives in `apps/web`; do not add Django template frontend flows here.

## Commands

```bash
pip install -e .[dev]
playwright install chromium  # headless render fallback for enrich_pages
prek run --all-files
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py runserver
```

## Architecture

- Business workflows: `core/services/` and `scrapers/services.py`.
- DTOs: `core/dtos.py` and `scrapers/dtos.py`.
- Public catalog and alerts: REST.
- Local product review: GraphQL in `scrapers/graphql/`, protected with `IsAuthenticatedWithAPIKey`.
- Review clients run on an operator workstation. The API owns queue discovery,
  targeted checkout, resume, heartbeat, release, extraction staging, duplicate
  search, and explicit approval; it does not host chat or model orchestration.
- Query composition belongs in `selectors.py`.
- Product, nutrition, component, flavor, brand, store, tag, category, alert subscriber, and API key management is manager-facing through Django admin.
- `ProductStore` is managed through the `ProductAdmin` inline, not as direct CRUD.
- Extraction staging only writes review data. `approveScrapedItem` is the sole
  remote review operation that may link an offer or create an unpublished
  catalog product, and it requires an item already staged in `review`.
- See `docs/domain.md` for review transitions, retry semantics, and the boundary
  between remote approval and detailed catalog curation in admin.

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
- Keep production host, TLS, cookie, and GraphQL permission settings explicit.
