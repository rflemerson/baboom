@/AGENTS.md

---

# Web Frontend Guide

## Scope

- This directory contains the public web frontend.
- Stack: Vue 3, Vite, TypeScript, Vue Router, Pinia.
- Data access should happen through the Django GraphQL API exposed by `apps/api`.
- Django admin stays in `apps/api`; do not recreate admin/backoffice flows here.

## GraphQL Client

- Use Apollo Client with `@vue/apollo-composable`.
- Keep Apollo on the `3.x` line when using `@vue/apollo-composable@4.x`.
- Do not upgrade to Apollo Client 4 without checking official Vue Apollo compatibility first.

## Styling Stack

- Use Tailwind CSS integrated through the official Vite plugin.
- Use Sass for shared tokens, complex component styles, and cases where utility classes become noisy.
- Keep Tailwind as the default styling tool for layout, spacing, responsive behavior, and fast iteration.
- Keep Sass small and intentional. Do not rebuild a full utility system on top of Tailwind.
- Prefer local `<style lang="scss" scoped>` blocks for component-specific Sass.
- Keep global styling limited to app-level files in `src/assets/`.

## Icons

- Use `lucide-vue-next`.
- Import icons directly by name from `lucide-vue-next`; do not import the entire icon set.
- Prefer explicit icon imports per component to preserve tree-shaking.
- Add `aria-label` when an icon conveys meaning on its own.

## Workflow

```bash
# Install deps
cd apps/web && npm install

# Dev server
cd apps/web && npm run dev

# Type-check
cd apps/web && npm run type-check

# Unit tests
cd apps/web && npm run test:unit

# E2E tests
cd apps/web && npm run test:e2e

# Lint
cd apps/web && npm run lint

# Format
cd apps/web && npm run format

# Tailwind / Sass / icons deps
cd apps/web && npm install tailwindcss @tailwindcss/vite lucide-vue-next
cd apps/web && npm install -D sass
```

## Conventions

- Prefer Composition API with `<script setup lang="ts">`.
- Keep route components under `src/views/`.
- Keep reusable UI under `src/components/`.
- Keep GraphQL documents under `src/graphql/`.
- Keep Apollo setup under `src/lib/`.
- Use environment variables with the `VITE_` prefix only.
- Keep global design tokens in `src/assets/`.
- Keep icon usage explicit and local to the consuming component.

## Vue Best Practices

- Use multi-word component names for user-defined components. `App` is the only normal exception.
- Define props with explicit types. Do not use string-array props in committed code.
- Always use a stable `:key` with `v-for`.
- Do not put `v-if` and `v-for` on the same element. Filter in a computed value or move `v-if` to a wrapper.
- Keep styles scoped for normal components. Global styles should live only in app-level or layout-level files.
- Prefer `computed` for derived state. Use `watch` or `watchEffect` for side effects, async reactions, and integration with external systems.
- Keep watchers small and purposeful. If logic starts looking like state derivation, move it to `computed`.
- Extract reusable stateful logic into composables under `src/composables/` and name them with the `useX` convention.
- In composables, register and clean up side effects with lifecycle hooks (`onMounted`, `onUnmounted`) instead of leaving global listeners around.
- Keep props as stable as possible to avoid unnecessary child updates.
- Prefer route-level code splitting for non-critical pages.
- Keep templates simple. Move transformation and branching logic into script/computed values instead of stacking logic in markup.
- Prefer explicit emits and typed payloads for component events.
- Keep business rules on the API side. Vue should orchestrate UI state and presentation, not recreate backend decisions.

## Integration Rules

- Start with simple read queries before building complex screens.
- Reuse GraphQL schema names as much as possible in frontend types and naming.
- Do not duplicate business logic from Django in Vue unless it is purely presentational.
- If CORS or auth blocks requests, fix the API boundary instead of adding frontend hacks.

## Tailwind / Sass Notes

- Tailwind should be imported once in the main CSS entry file with `@import "tailwindcss";`.
- Prefer utility classes first, then extract repetition into Vue components before reaching for custom Sass.
- Use Sass nesting sparingly; avoid deep selector chains.
- Keep theme decisions in CSS variables when possible so Tailwind utilities and Sass can share the same design language.

## Documentation Sources

- Tailwind CSS with Vite: https://tailwindcss.com/docs/installation/using-vite
- Sass guide: https://sass-lang.com/guide/
- Lucide Vue Next: https://lucide.dev/guide/packages/lucide-vue-next

## Documentation Policy

- If frontend tooling or integration patterns change, update this file in the same task.
