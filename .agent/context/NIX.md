---
description: Nix Environment Reference
alwaysApply: true
applyTo: "**"
---

# Nix Environment Reference

- [IDX Customization](https://developers.google.com/idx/guides/customize-idx-env)
- [Nix Packages](https://search.nixos.org/packages)

## Overview
This project uses **Nix** via Google IDX to provide a reproducible development environment. The configuration lives in `.idx/dev.nix`.

**CRITICAL RULE**: Do not manually install system packages or global Python packages. Update `dev.nix` instead.

## Core Components

### 1. Packages (`packages` list)
-   **Python**: `pkgs.python314` (3.14.*)
-   **Linters**: `pkgs.ruff`, `pkgs.djlint`
-   **Services**: Postgres 15, Redis.

### 2. Services
Services are managed declaratively in the `services` block.
-   **Postgres**: Enabled (`pkgs.postgresql_15`).
-   **Redis**: Enabled.

### 3. Lifecycle Hooks (`idx.workspace`)
-   **onCreate**: Runs once on environment creation.
    -   Installs API dependencies: `cd apps/api && pip install -e .[dev]`
    -   Migrates DB: `python apps/api/manage.py migrate`
-   **onStart**: Runs every time the workspace starts.
-   **Previews**: Configures the web preview (Django runserver on `$PORT`).

## Managing Dependencies

### Python Packages
1.  Add dependency to `apps/api/pyproject.toml`.
2.  Run `cd apps/api && pip install -e .` (or `.[dev]`).
3.  **Do NOT** use `requirements.txt`.

### System Packages
1.  Search for the package on [NixOS Search](https://search.nixos.org/packages).
2.  Add it to the `packages` list in `.idx/dev.nix`.
3.  Rebuild the environment (IDX Command Palette > "Rebuild Environment").
