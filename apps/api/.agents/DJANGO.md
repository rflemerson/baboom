# Django Backend

## Direction

- Keep the backend centered on Django admin, GraphQL, services, selectors, and models.
- Do not rebuild the removed public Django frontend.
- Prefer domain names that reflect the current GraphQL/Vue architecture instead of old template-view names.

## Architecture

- Business logic goes in `services/`.
- Read/query composition goes in `selectors.py`.
- Filtering logic goes in `filters.py`.
- GraphQL boundary stays thin in `core/graphql/`.
- Admin customizations should stay typed and light.

## Refactor rules

- Do not add `# noqa`, `type: ignore`, or rule disables to get past lint.
- Prefer real refactors:
  - `ANN*`: add concrete types
  - `TC*`: move annotation-only imports into `if TYPE_CHECKING:`
  - `RUF012`: annotate mutable class metadata with `ClassVar` or use immutable tuples
  - `PERF*`: simplify loops if readability stays good
- Prefer plain `assert` in tests where the active lint stack expects it.

## GraphQL

- Keep queries and mutations thin.
- Normalize arguments at the boundary, then delegate to selectors/services.
- If a resolver gets too many arguments, introduce a typed input object instead of suppressing the lint warning.
