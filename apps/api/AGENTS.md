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
.venv/bin/python manage.py runserver
```

## Architecture

- Business workflows: `core/services/` and `scrapers/services.py`.
- DTOs: `core/dtos.py` and `scrapers/dtos.py`.
- Public catalog and alerts: REST.
- Scrapers retain `ScrapedPage` metadata, structured data and captured HTML;
  humans inspect captured pages and curate the catalog through Django admin.
- The Django enrichment task uses an HTTP capture. Interactive browser
  investigation belongs to the local browser client, not this application.
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
