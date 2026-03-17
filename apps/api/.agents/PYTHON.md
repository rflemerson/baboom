# Python and Typing

## Packaging

- `apps/api/pyproject.toml` is the source of truth for dependencies.
- `apps/api/ruff.toml` holds Ruff configuration.
- `apps/api/prek.toml` holds hook orchestration.

## Typing rules

- Public functions must have explicit parameter and return types.
- Avoid `Any`; prefer concrete types, generics, `TypedDict`, `Protocol`, or narrow framework types.
- Use `from __future__ import annotations` where it helps avoid runtime cycles.
- Move annotation-only imports into `TYPE_CHECKING`.
- Keep Django overrides typed too: `save`, `clean`, admin hooks, command methods, queryset helpers, Strawberry resolvers.
- Prefer typed objects over long loosely related parameter lists.

## Refactor style

- Fix the code instead of silencing the tool.
- Prefer immutable metadata where possible.
- Use `ClassVar[...]` for mutable class-level metadata that belongs on the class.
- Keep tests explicit and focused on behavior.
