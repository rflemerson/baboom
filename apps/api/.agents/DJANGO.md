# Django Backend

## Direction

- Keep the backend centered on Django admin, GraphQL, services, selectors, and models.
- Do not rebuild the removed public Django frontend.
- Prefer domain names that reflect the current GraphQL/Vue architecture instead of old template-view names.

## Architecture

- Business logic goes in `core/services.py`.
- Read/query composition goes in `selectors.py`.
- Filtering logic goes in `filters.py`.
- GraphQL boundary stays thin in `core/graphql/`.
- Admin customizations should stay typed and light.

## Project patterns

- Prefer explicit use-case classes for business workflows:
  - `ProductCreateService`
  - `ProductMetadataUpdateService`
  - `ComboResolutionService`
  - `ProductNutritionService`
  - `AlertSubscriptionService`
- Prefer direct class usage at call sites over thin wrapper functions.
- Keep orchestration at the service layer and keep models focused on invariants and persistence.
- Keep GraphQL mutations as boundary adapters: map input, call a use-case class, map output.
- Prefer typed DTOs between the GraphQL boundary and services instead of passing raw
  `dict[str, Any]` payloads into business workflows.
- Prefer exact identifier matching over fuzzy matching when linking domain entities automatically.
- Avoid “clever” abstractions that hide business rules; favor explicit names and stable control flow.
- Treat the API code as portfolio-quality:
  - no legacy leftovers
  - no cosmetic wrappers
  - no broad utility dumping ground
  - no implicit magic when an explicit rule is clearer

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
