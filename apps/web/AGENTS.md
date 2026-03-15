@/AGENTS.md
@/apps/web/agents/APOLLO.md
@/apps/web/agents/GRAPHQL_CODEGEN.md
@/apps/web/agents/STYLING.md
@/apps/web/agents/VUE_PRACTICES.md

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

# Lint
cd apps/web && npm run lint

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

## Integration Rules

- Start with simple read queries before building complex screens.
- Reuse GraphQL schema names as much as possible in frontend types and naming.
- Do not duplicate business logic from Django in Vue unless it is purely presentational.
- If CORS or auth blocks requests, fix the API boundary instead of adding frontend hacks.

## Documentation Policy

- The files under `apps/web/agents/` are the focused frontend references.
- Keep each file about one topic.
- Every file in `apps/web/agents/` must include source links for the guidance it contains.
- If frontend tooling or integration patterns change, update the relevant topic file in the same task.
- Do not hand-edit files under `src/gql/`; regenerate them with `npm run graphql-codegen`.
