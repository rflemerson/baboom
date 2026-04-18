# API Guide

## Scope

- This directory contains the Django API, GraphQL schema, admin, and scraping integration.
- The public frontend lives in `apps/web`; do not reintroduce Django template frontend work here.
- Keep this file updated when architecture or tooling changes.

## Workflow

```bash
cd apps/api && pip install -e .[dev]
cd apps/api && prek run --all-files
cd apps/api && .venv/bin/python manage.py check
cd apps/api && .venv/bin/python manage.py test
cd apps/api && .venv/bin/python manage.py runserver
```

## Architecture

- Core business workflows live in `core/services.py`.
- Service DTOs live in `core/dtos.py`; scraper DTOs live in `scrapers/dtos.py`.
- GraphQL stays thin:
  - `core/graphql/` and `scrapers/graphql/` map input, call services/selectors, map output.
- Read/query composition lives in `selectors.py`, not in GraphQL and not in form-style filters.
- Scraper workflows live in `scrapers/services.py`.
- Agent extraction review staging lives in `scrapers`:
  - persistence model: `ScrapedItemExtraction`
  - service: `ScrapedItemExtractionSubmitService`
  - GraphQL mutation: `submitAgentExtraction`
- Agent extraction staging must not create or link catalog products directly.
- Admin forms/formsets live in `core/forms.py`.
- Admin-to-service mapping helpers live in `core/admin_mappers.py`.
- Domain docs live in `docs/domain/`; scraper strategy docs live in `docs/scrapers/`.

## Project Patterns

- Prefer explicit use-case classes over wrapper helpers.
- Keep models focused on invariants and persistence.
- Keep orchestration in services.
- Prefer typed DTOs over `dict[str, Any]`.
- Prefer exact identifier matching over fuzzy matching.
- Treat `ProductAdmin` as the official manager-facing workflow for product metadata, nutrition, and store listings.
- Wrap manager-facing admin save flows in a transaction when one save coordinates multiple related writes.

## Typing and Refactors

- Public functions need explicit parameter and return types.
- Avoid `Any`; prefer concrete types and narrow framework types.
- Move annotation-only imports into `TYPE_CHECKING`.
- Use `ClassVar[...]` for mutable class metadata.
- Do not use `# noqa`, `type: ignore`, or broad ignore globs to bypass lint.
- Prefer plain `assert` in tests.

## Quality and Security

- Run `prek run --all-files` before finishing substantial changes.
- Do not use `--no-verify` when committing.
- Review files modified automatically by hooks and rerun until clean.
- Keep GraphQL permissions explicit.
- Do not log secrets, API keys, or sensitive personal data.
- Keep production host/TLS/cookie settings explicit and strict.
- Do not commit Django `SECRET_KEY` values; load them from env and only use generated runtime fallbacks for local development.
