---
description: Python Packaging Reference
alwaysApply: true
applyTo: "**"
---

# Python Packaging Reference

## Overview
This project uses modern Python packaging standards (PEP 621) via `pyproject.toml`.

**CRITICAL RULE**: `pyproject.toml` is the Single Source of Truth for dependencies. **Delete** `requirements.txt` if found.

## Configuration (`pyproject.toml`)

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
-   **Install/Sync**: `pip install -e .[dev]`
-   **Unlock/Upgrade**: `pip install --upgrade package_name` (then update `pyproject.toml` if pinning is needed).
-   **Add Dependency**: Add it to `pyproject.toml` manually, then run `pip install -e .`.

## Tool Configuration
All tool configuration (Ruff, MyPy, DjLint, Coverage) lives in `pyproject.toml` under `[tool.*]` sections. Avoid creating separate config files like `.flake8` or `pytest.ini` unless strictly necessary.
