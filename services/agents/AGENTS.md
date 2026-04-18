# Agents Service Guide

Use this file as the minimal context for `services/agents`.

## Load On Demand

Read these docs only when they are relevant:

- `docs/pipeline.md`
  current pipeline step by step
- `docs/architecture.md`
  architecture rules, Dagster boundaries, and preferred patterns
- `README.md`
  local setup, environment variables, and service runtime

## Current Scope

- Entrypoint Dagster: `agents/definitions.py`
- Dagster code: `agents/defs/`
- Deterministic acquisition: `agents/acquisition.py`
- Non-deterministic extraction: `agents/extraction.py`
- Model wrappers: `agents/brain.py`
- Shared schema: `agents/schemas.py`

## Current Pipeline Contract

- The Django backend is the source of truth for `api_context` and
  `html_structured_data`.
- Dagster consumes `sourcePageApiContext` as its primary deterministic input.
- Each page produces exactly one root `ExtractedProduct`.
- Combos and kits use `children`; there is no `items`, `components`, or
  `is_combo`.
- The only extraction flow is:
  `image_report` reads the images once and returns ordered text,
  then `product_analysis` converts that text into schema.
- The final stage is `extraction_handoff`: it only returns the extracted
  payload and does not create catalog data.

## Working Rules

- Keep `agents/definitions.py` thin.
- Keep Dagster logic in `agents/defs/` and testable non-Dagster logic in plain
  Python modules.
- Prefer removing dead paths and stale abstractions over documenting them.
- Update this documentation in the same change when the architecture changes.

## Commands

```bash
Test (Pytest): PYTHONPATH=services/agents:. pytest services/agents/agents/tests -q
Coverage (Pytest): PYTHONPATH=services/agents:. pytest services/agents/agents/tests --cov=agents --cov-report=term-missing
Lint Agents (Just): just agents-lint
Orchestration: PYTHONPATH=services/agents:. dagster dev -m agents.definitions
Agents Isolated Deps: cd services/agents && python -m venv .venv && source .venv/bin/activate && pip install -e .
```
