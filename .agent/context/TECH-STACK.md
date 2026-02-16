# Technology Stack

## Core
- **Language:** Python 3.14.*
- **Framework:** Django 6.0.* (Dec 2025 Release)
- **Frontend Stack:** TALL-Django (Tailwind, Alpine.js, Django Templates)

## Data & Storage
- **Database:** PostgreSQL 15.* (via Nix)
- **Cache/Broker:** Redis (via Nix)

## Core Dependencies
These packages are required for the application runtime.
- **Server:** `gunicorn`, `whitenoise`
- **Database Driver:** `psycopg`
- **Utilities:** `requests`, `urllib3`, `Pillow`, `django-environ`
- **Django Extensions:**
    - `django-filter`
    - `django-simple-history`
    - `django-treebeard`
    - `django-nested-admin`
    - `django-htmx`
    - `django-widget-tweaks`

## Async & Background Tasks
- **Engine:** `celery`, `django-celery-results`, `django-celery-beat`
- **Scraping:** `playwright`, `beautifulsoup4`, `lxml`, `curl_cffi`

## Quality Assurance & Development
Tools configured in `.pre-commit-config.yaml` and `pyproject.toml`.
- **Linter (Ruff):** 0.14.* (Target: py314)
- **Template Linter (DjLint):** 1.36.*
- **Template Formatter (DjHTML):** 3.0.*
- **Template Linter (CurlyLint):** 0.13.*
- **Type Checker (MyPy):** 1.19.*
- **Dependency Checker (Deptry):** 0.24.*
- **Security (Safety):** *
- **Testing:** `factory-boy`

## Automation & Orchestration
- **Workflow Engine:** Dagster
- **Environment Manager:** Nix (via `.idx/dev.nix`)
- **QA:** Scripts for verification before commit.
