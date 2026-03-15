# Styling

## Base stack

- Tailwind CSS is the primary styling tool.
- Sass is allowed for shared tokens, complex component styles, and cases where utility classes become noisy.
- Keep Tailwind imported once from the main CSS entry file.

## Current project pattern

- Global Tailwind entry lives in `src/styles.css`.
- Prefer utility classes first.
- Reach for Sass only when the component benefits from local structure or repeated styling logic.

## Guidance

- Keep global styles minimal.
- Keep component-level Sass scoped.
- Avoid rebuilding a separate design system on top of Tailwind too early.
- Prefer extracting repeated markup into Vue components before extracting repeated utility sets into custom classes.

## Sources

- Tailwind with Vite: https://tailwindcss.com/docs/installation/using-vite
- Tailwind utility-first workflow: https://tailwindcss.com/docs/styling-with-utility-classes
- Sass guide: https://sass-lang.com/guide/
