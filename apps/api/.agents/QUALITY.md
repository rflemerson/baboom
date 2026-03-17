# API Quality and Hooks

## Hooks

- Run `prek run --all-files` in `apps/api`.
- Do not use `--no-verify` when actually committing.
- If a hook edits files automatically, review the diff and rerun the hook until it passes.

## Non-negotiable policy

- Do not use `noqa`, `type: ignore`, or broad ignore globs to get past lint unless the code is generated or the boundary truly requires it.
- Prefer fixing the architecture and code shape to satisfy the active rules.
- If migrations or generated files need exclusion, do it once in tool configuration, not with per-line suppression.

## Current tooling

- Ruff
- Ruff format
- Deptry
- Vulture
- Interrogate
