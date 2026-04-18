# Agents Architecture

This document holds the more detailed architecture context for
`services/agents`. It does not need to be loaded by default; use it when the
task involves structural refactors, sensors, assets, or Dagster organization.

## Goal

The agents service should stay simple:

- Dagster orchestrates
- Python helpers transform data
- LLMs extract information
- the backend decides catalog persistence

## Preferred Structure

```text
agents/
  definitions.py
  defs/
    assets.py
    pipeline.py
    sensors.py
  acquisition.py
  extraction.py
  brain.py
  prompts/
  schemas.py
  tests/
```

## Boundaries

### `definitions.py`

- exposes a single `Definitions`
- does wiring only
- contains no business logic

### `defs/`

- holds Dagster objects only
- assets, sensors, jobs, and run config
- should not accumulate complex transformation logic

### `acquisition.py`

- deterministic stage
- normalizes `ScrapedItem` + `ScrapedPage`
- reads `sourcePageApiContext` and `sourcePageHtmlStructuredData`
- prepares JSON context and images in stable order

### `extraction.py`

- non-deterministic stage
- runs `image_report`
- converts the ordered image report into `ExtractedProduct`
- loads prompts

### `brain.py`

- thin wrappers for model calls
- no implicit schema or prompt fallback
- exposes one multimodal wrapper for `image_report`
- exposes one text wrapper for `product_analysis`

### `schemas.py`

- shared Pydantic contracts
- must remain importable outside Dagster

## Pipeline Rules

- A page produces one root product.
- If there is a combo or kit, the root product contains `children`.
- `children` uses the same schema recursively.
- The pipeline does not decide catalog identity.
- The pipeline does not create products, variants, or components.
- The pipeline ends at `extraction_handoff`.

## Sensor Rules

- a sensor only orchestrates
- it may fetch work, validate the minimum payload, and emit `RunRequest`
- it must not carry heavy domain logic

## Asset Rules

- each asset represents one clear boundary
- prefer explicit inputs and outputs
- isolate external calls and LLMs to improve retries and observability

## Testing Rules

- `defs.validate_loadable()` is a required structural test
- pure helpers should be tested without Dagster
- asset tests should focus on contract and failure cases, not framework internals

## Decision Rule

When a refactor is ambiguous, prefer the option that leaves the code:

1. more testable outside Dagster
2. more explicit about boundaries
3. less coupled to transport details
4. with less indirection
