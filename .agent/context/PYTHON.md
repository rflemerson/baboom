---
description: Python Packaging Reference
alwaysApply: true
applyTo: "**"
---

# Python Packaging Reference

## Overview
This project uses modern Python packaging standards (PEP 621) via `apps/api/pyproject.toml`.

**CRITICAL RULE**: `apps/api/pyproject.toml` is the Single Source of Truth for API dependencies. **Delete** `requirements.txt` if found.

## Configuration (`apps/api/pyproject.toml`)

### 1. Metadata
-   **Requires Python**: `>= 3.14`
-   **Build System**: `hatchling`

### 2. Dependencies (`project.dependencies`)
List of runtime dependencies.
-   **Django Ecosystem**: `django`, `django-filter`, `django-htmx`, `django-simple-history`.
-   **Async/Tasks**: `celery`, `redis`.
-   **Scraping**: `playwright`, `beautifulsoup4`.
-   **Utils**: `requests`, `pillow`.

### 3. Dev Dependencies (`project.optional-dependencies.dev`)
List of development/testing tools.
-   **QA**: `ruff`, `pre-commit`, `mypy`, `djlint`.
-   **Testing**: `factory-boy`, `django-stubs`.

## Usage
-   **Install/Sync**: `cd apps/api && pip install -e .[dev]`
-   **Unlock/Upgrade**: `pip install --upgrade package_name` (then update `apps/api/pyproject.toml` if pinning is needed).
-   **Add Dependency**: Add it to `apps/api/pyproject.toml` manually, then run `cd apps/api && pip install -e .`.

## Tool Configuration
All API tool configuration (Ruff, MyPy, DjLint, Coverage) lives in `apps/api/pyproject.toml` under `[tool.*]` sections. Avoid creating separate config files like `.flake8` or `pytest.ini` unless strictly necessary.
