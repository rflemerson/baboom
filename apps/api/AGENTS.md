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
- Agent checkout/extraction/error reporting: GraphQL in `scrapers/graphql/`, protected with `IsAuthenticatedWithAPIKey`.
- Query composition belongs in `selectors.py`.
- Product, nutrition, component, flavor, brand, store, tag, category, alert subscriber, and API key management is manager-facing through Django admin.
- `ProductStore` is managed through the `ProductAdmin` inline, not as direct CRUD.
- Agent extraction staging must only write review data; catalog creation stays in admin workflows.

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
