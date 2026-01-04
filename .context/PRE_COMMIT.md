---
description: Pre-commit QA Reference
alwaysApply: true
applyTo: "**"
---

# Pre-commit QA Reference

- [Ruff Docs](https://docs.astral.sh/ruff/)
- [DjLint Docs](https://www.djlint.com/)

## Overview
Quality Assurance is enforced via `pre-commit` hooks. These checks run automatically on `git commit`.

**CRITICAL RULE**: Never bypass pre-commit hooks (`--no-verify`) unless absolutely necessary for a hotfix.

## Enabled Hooks

### 1. Ruff (Python Linter & Formatter)
-   **Config**: `pyproject.toml` (`[tool.ruff]`).
-   **Target**: Python 3.14.
-   **Rules**:
    -   `E`, `W`, `F` (Standard flake8/pycodestyle)
    -   `I` (Isort)
    -   `UP` (Pyupgrade - modern syntax)
    -   `DJ` (Django - specific best practices)
    -   `B` (Bugbear - clean code)
    -   `S` (Bandit - security)

### 2. DjLint (Template Linter)
-   **Config**: `pyproject.toml` (`[tool.djlint]`).
-   **Target**: `.html` files.
-   **Profile**: `django`.

### 3. DjHTML (Template Formatter)
-   **Target**: `.html` files.
-   **Action**: formatting indentation.

### 4. CurlyLint (Template Linter)
-   **Target**: `.html` files.
-   **Check**: Jinja/Django template syntax errors.

### 5. MyPy (Type Checker)
-   **Config**: `pyproject.toml` (`[tool.mypy]`).
-   **Plugins**: `django-stubs`, `pydantic`.
-   **Strictness**: `check_untyped_defs = true`.

### 6. Deptry (Dependency Checker)
-   **Target**: `pyproject.toml` vs imports.
-   **Check**: Unused dependencies, missing dependencies.

### 7. Safety (Security)
-   **Check**: Known vulnerabilities in installed packages.

## Workflow
1.  **Run All**: `pre-commit run --all-files`
2.  **Fix Issues**:
    -   **Ruff**: Auto-fix most issues.
    -   **MyPy**: Add type hints.
    -   **Deptry**: Remove unused packages from `pyproject.toml`.
