# Vue Practices

## Component rules

- Prefer Composition API with `<script setup lang="ts">`.
- Use multi-word names for user-defined components.
- Keep templates focused on presentation; move derived state into `computed` or composables.
- Keep props typed and explicit.

## State and reuse

- Use composables for stateful feature logic.
- Keep route-level concerns in views.
- Keep reusable presentation in domain components.
- Colocate unit tests with the file they cover using `*.spec.ts`.

## Rendering rules

- Always use stable `:key` values with `v-for`.
- Do not combine `v-if` and `v-for` on the same element.
- Prefer `computed` for derived state and `watch` for side effects.

## Sources

- Vue style guide: https://vuejs.org/style-guide/
- Vue computed: https://vuejs.org/guide/essentials/computed
- Vue watchers: https://vuejs.org/guide/essentials/watchers
- Vue composables: https://vuejs.org/guide/reusability/composables.html
- Vue performance best practices: https://vuejs.org/guide/best-practices/performance
