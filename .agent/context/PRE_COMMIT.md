---
description: Git Hook QA Reference
alwaysApply: true
applyTo: "**"
---

# Git Hook QA Reference

- [Ruff Docs](https://docs.astral.sh/ruff/)

## Overview
Quality Assurance is enforced via git hooks powered by `prek`. These checks run automatically on `git commit`.

**CRITICAL RULE**: Never bypass git hooks (`--no-verify`) unless absolutely necessary for a hotfix.

## Enabled Hooks

### 1. Ruff (Python Linter & Formatter)
-   **Hook Config**: `apps/api/prek.toml`, `services/agents/prek.toml`.
-   **Rule Config**: `apps/api/pyproject.toml` and `services/agents/pyproject.toml` (`[tool.ruff]`).
-   **Target**: Python 3.14.
-   **Rules**:
    -   `E`, `W`, `F` (Standard flake8/pycodestyle)
    -   `I` (Isort)
    -   `UP` (Pyupgrade - modern syntax)
    -   `DJ` (Django - specific best practices)
    -   `B` (Bugbear - clean code)
    -   `S` (Bandit - security)

## Workflow
1.  **Run All**: `prek run --all-files`
2.  **Fix Issues**:
    -   **Ruff**: Auto-fix most issues.
