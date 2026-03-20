@/AGENTS.md
@/apps/web/.agents/APOLLO.md
@/apps/web/.agents/GRAPHQL_CODEGEN.md
@/apps/web/.agents/STYLING.md
@/apps/web/.agents/VUE_PRACTICES.md

---

# Web Frontend Guide

## Scope

- This directory contains the public web frontend.
- Stack: Vue 3, Vite, TypeScript, Vue Router, Pinia.
- Data access should happen through the Django GraphQL API exposed by `apps/api`.
- Django admin stays in `apps/api`; do not recreate admin/backoffice flows here.

## Workflow

```bash
# Install deps
cd apps/web && npm install

# Dev server
cd apps/web && npm run dev

# Type-check
cd apps/web && npm run type-check

# Unit tests
cd apps/web && npm run test:unit -- --run

# E2E tests
cd apps/web && npm run test:e2e

# GraphQL Codegen
cd apps/web && CODEGEN_API_KEY=your-local-api-key npm run graphql-codegen

# Prek hooks for web workspace
cd apps/web && prek run --all-files

# Lint
cd apps/web && npm run lint

# Unused files / exports / dependencies
cd apps/web && npm run knip

# Format
cd apps/web && npm run format
```

## Project Structure

- Keep route components under `src/views/`.
- Keep reusable UI under `src/components/`, grouped by domain (`catalog/`, `alerts/`, `layout/`, `ui/`).
- Keep GraphQL documents under `src/graphql/`, split by operation type (`queries/`, `mutations/`, `fragments/`).
- Prefer `.graphql` files for operations instead of inline document strings in TypeScript.
- Keep GraphQL client setup under `src/graphql/client/`.
- Keep generated GraphQL artifacts under `src/gql/`.
- Keep frontend runtime types under `src/types/`.
- Keep stateful integration logic under `src/composables/`.
- Colocate unit tests with the file they cover using `*.spec.ts`.
- Prefer shared UI primitives under `src/components/ui/` before re-implementing the same interaction pattern in feature components.

## Integration Rules

- Start with simple read queries before building complex screens.
- Reuse GraphQL schema names as much as possible in frontend types and naming.
- Do not duplicate business logic from Django in Vue unless it is purely presentational.
- If CORS or auth blocks requests, fix the API boundary instead of adding frontend hacks.
- Keep GraphQL operations in `.graphql` files under `src/graphql/`; generate typed documents with Codegen and consume those documents from composables.
- Keep feature components focused on presentation; use composables for query state, filters, and mutations.
- Keep shared styling rules in `src/theme.scss`; prefer semantic classes and reusable UI components over one-off per-component styling hacks.
- Prefer Playwright request mocking for frontend-only E2E coverage of catalog and alerts flows so the tests do not depend on a live Django server.
- Keep `Knip` enabled for unused files, unused exports, and dependency drift; fix the code or package manifest instead of ignoring findings.
- Keep typed ESLint rules enabled for async/control-flow smells; fix promise handling and unnecessary conditions instead of suppressing the rule.

## Documentation Policy

- The files under `apps/web/.agents/` are the focused frontend references.
- Keep each file about one topic.
- Every file in `apps/web/.agents/` must include source links for the guidance it contains.
- If frontend tooling or integration patterns change, update the relevant topic file in the same task.
- Do not hand-edit files under `src/gql/`; regenerate them with `npm run graphql-codegen`.
- Keep frontend prek hooks in `apps/web/prek.toml`; use `npm`-backed local hooks for format, lint, type-check, and unit tests.
- Keep Stylelint naming rules enabled; fix naming to the linter instead of disabling rules or broadening ignore files.
