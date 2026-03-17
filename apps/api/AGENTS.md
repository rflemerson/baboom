@/apps/api/.agents/DJANGO.md
@/apps/api/.agents/PYTHON.md
@/apps/api/.agents/QUALITY.md
@/apps/api/.agents/SECURITY.md

---

# API Guide

## Scope

- This directory contains the Django API, GraphQL schema, admin, and scraping integration.
- The public frontend lives in `apps/web`; do not reintroduce public template frontend work here.

## Workflow

```bash
# Install deps
cd apps/api && pip install -e .[dev]

# Run checks
cd apps/api && prek run --all-files
cd apps/api && .venv/bin/python manage.py check

# Run tests
cd apps/api && .venv/bin/python manage.py test

# Run server
cd apps/api && .venv/bin/python manage.py runserver
```

## Local docs

- Keep Django, typing, QA, and security guidance in `apps/api/.agents/`.
- Update these docs when refactors or tooling policy changes.
