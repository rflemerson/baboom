# Styling

## Base stack

- Tailwind CSS is the primary styling tool.
- Sass is allowed for shared tokens, complex component styles, and cases where utility classes become noisy.
- Keep Tailwind imported once from the main CSS entry file.

## Current project pattern

- Global Tailwind entry lives in `src/styles.css`.
- Prefer utility classes first.
- Reach for Sass only when the component benefits from local structure or repeated styling logic.
- Prettier uses `prettier-plugin-tailwindcss` to sort Tailwind classes automatically.
- Do not add `eslint-plugin-tailwindcss` right now; the current released plugin line targets Tailwind 3, while this project uses Tailwind 4.

## Guidance

- Keep global styles minimal.
- Keep component-level Sass scoped.
- Avoid rebuilding a separate design system on top of Tailwind too early.
- Prefer extracting repeated markup into Vue components before extracting repeated utility sets into custom classes.
- Let Prettier handle Tailwind class ordering instead of trying to enforce that through custom manual conventions.
- If Tailwind-specific linting is revisited later, re-check Tailwind 4 compatibility first instead of forcing the older ESLint plugin into the toolchain.

## Sources

- Tailwind with Vite: https://tailwindcss.com/docs/installation/using-vite
- Tailwind utility-first workflow: https://tailwindcss.com/docs/styling-with-utility-classes
- Tailwind class sorting with Prettier: https://tailwindcss.com/blog/automatic-class-sorting-with-prettier
- Tailwind Prettier plugin whitespace and duplicate cleanup: https://tailwindcss.com/blog/2024-05-30-prettier-plugin-collapse-whitespace
- ESLint plugin for Tailwind CSS: https://github.com/francoismassart/eslint-plugin-tailwindcss
- Sass guide: https://sass-lang.com/guide/
