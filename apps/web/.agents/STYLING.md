# Styling

## Base stack

- Tailwind CSS is the primary styling tool.
- Sass is allowed for shared tokens, complex component styles, and cases where utility classes become noisy.
- Stylelint is enabled for `css`, `scss`, and `vue` style blocks in `apps/web`.
- Keep Tailwind imported once from the main CSS entry file.

## Current project pattern

- Global Tailwind entry lives in `src/styles.css`.
- `src/theme.scss` only `@use`s the shared partials under `src/styles/`:
  `tokens.scss` (colors, theme timing, `--app-control-height`: 40px on touch,
  36px from 768px), `base.scss` (page, shell, copy colors, panels, skeleton,
  status), `controls.scss` (`app-button` and its color modifiers, `app-input`),
  `menu.scss` (`app-menu`, a `<details>` with a floating `__panel` and
  `__action` rows) and `dialog.scss`.
- A style used by one component lives in that component's
  `<style scoped lang="scss">` (table, cards, pagination, catalog toolbar,
  `BaseSelect`, header), never in the theme.
- Buttons have one size, from `--app-control-height`; modifiers only change
  color (`--primary`, `--secondary`, `--ghost`, `--accent`) or make an icon
  square (`--icon-square`).
- The app theme is controlled through `document.documentElement.dataset.theme` and toggled by `useThemeMode`.
- Prefer utility classes first.
- Reach for Sass when the component or the whole app needs semantic tokens, shared UI primitives, or repeated styling logic.
- Prettier uses `prettier-plugin-tailwindcss` to sort Tailwind classes automatically.
- Stylelint runs through `npm run lint:styles` and is included in the main `npm run lint` pipeline.
- Keep Stylelint naming rules enabled. Do not add `stylelint-disable`, do not null out naming rules, and do not broaden ignore files to work around violations. Fix class names and keyframe names to match the project pattern instead.
- Do not add `eslint-plugin-tailwindcss` right now; the current released plugin line targets Tailwind 3, while this project uses Tailwind 4.

## Guidance

- Keep global styles minimal.
- Keep component-level Sass scoped.
- Avoid rebuilding a separate design system on top of Tailwind too early.
- Prefer extracting repeated markup into Vue components before extracting repeated utility sets into custom classes.
- Put theme colors and reusable UI primitives in `src/styles/` so visual changes cascade from one place; a class only one component uses belongs to that component.
- Keep the light theme as the default token set in `:root` and add dark overrides under `:root[data-theme='dark']`.
- Use Tailwind primarily for layout, spacing, sizing, and responsive behavior.
- Use semantic classes such as buttons, panels, inputs, and dialog shells to avoid long repeated class strings in templates.
- Theme-sensitive transitions use the shared `--app-theme-duration` and `--app-theme-easing` tokens so light/dark toggles stay synchronized.
- For empty, error, or other catalog state panels, prefer a shared semantic class such as `app-state-panel` instead of reassembling dashed borders and muted surfaces per component.
- When controls should share a size, use `--app-control-height` instead of per-component heights.
- Keep theme-toggle animation timing centralized in `src/styles/tokens.scss` with shared duration/easing tokens so dark/light transitions stay visually synchronized across surfaces, controls, and text.
- For shared modal behavior, prefer `BaseModal` so keyboard handling, focus management, and overlay behavior stay consistent.
- Let Prettier handle Tailwind class ordering instead of trying to enforce that through custom manual conventions.
- Keep CSS class names in the semantic project namespace: `app-*` for shared UI and layout primitives, `alert-*` for alert-specific local styles, optional `__element` and `--modifier` suffixes, plus `is-*` for state classes.
- Keep `@keyframes` names in the same namespace, such as `app-*` or `alert-*`.
- If Tailwind-specific linting is revisited later, re-check Tailwind 4 compatibility first instead of forcing the older ESLint plugin into the toolchain.

## Sources

- Vue scoped CSS: https://vuejs.org/api/sfc-css-features.html#scoped-css
- WCAG 2.5.8 target size: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

- Tailwind with Vite: https://tailwindcss.com/docs/installation/using-vite
- Stylelint getting started: https://stylelint.io/user-guide/get-started
- Tailwind utility-first workflow: https://tailwindcss.com/docs/styling-with-utility-classes
- Tailwind class sorting with Prettier: https://tailwindcss.com/blog/automatic-class-sorting-with-prettier
- Tailwind Prettier plugin whitespace and duplicate cleanup: https://tailwindcss.com/blog/2024-05-30-prettier-plugin-collapse-whitespace
- ESLint plugin for Tailwind CSS: https://github.com/francoismassart/eslint-plugin-tailwindcss
- stylelint-config-html: https://github.com/ota-meshi/stylelint-config-html
- Sass guide: https://sass-lang.com/guide/
