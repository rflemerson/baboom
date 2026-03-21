# Agents Service Guide (Dagster)

This guide defines the preferred architecture and working rules for
`services/agents`.

It is intentionally opinionated toward Dagster best practices from the official
documentation, even when the current codebase has not fully caught up yet.
Treat this file as the target shape for future refactors.

## Scope

- Package entrypoint: `agents/definitions.py`
- Dagster-facing modules: `agents/defs/**`
- Shared contracts: `agents/contracts/**`
- Deterministic acquisition logic: `agents/acquisition/**`
- Non-deterministic extraction logic: `agents/extraction/**`
- Agent/model wrappers: `agents/brain/**`
- API publishing logic: `agents/publishing/**`
- Shared non-Dagster support logic: `agents/tools/**`, `agents/schemas/**`,
  `agents/storage/**`

## Official references

- Project organization:
  https://docs.dagster.io/guides/build/projects/project-structure/organizing-dagster-projects
- `Definitions` API:
  https://docs.dagster.io/api/dagster/definitions
- Sensors:
  https://docs.dagster.io/guides/automate/sensors
- Official quickstart reference repo:
  https://github.com/dagster-io/dagster-quickstart

## Core Dagster rules

1. Expose one loadable `Definitions` object per code location.
2. Keep `agents/definitions.py` thin. It should wire assets, jobs, sensors,
   schedules, and resources, not implement business logic.
3. Keep Dagster-specific code under `agents/defs/`.
4. Keep non-Dagster logic in plain Python modules so it stays easy to test
   without Dagster machinery.
5. Prefer a single code location unless dependency boundaries or team ownership
   clearly require multiple locations.

## Preferred structure

```text
agents/
  definitions.py
  contracts/
  defs/
    assets/
    resources/
    sensors/
    jobs/
  acquisition/
  extraction/
  publishing/
  brain/
  prompts/
  schemas/
  storage/
  tools/
  tests/
```

Notes:

- `defs/` is for Dagster-facing objects only.
- `contracts/` defines the value objects passed between stages.
- `acquisition/` owns deterministic source preparation up to prepared OCR
  inputs.
- `extraction/` owns the non-deterministic OCR and structured-analysis flow.
- `publishing/` owns API synchronization after analysis is finalized.
- `brain/` is limited to agent/model wrappers and prompt-loading glue.
- `brain/`, `tools/`, `schemas/`, and `storage/` should remain importable and
  testable outside Dagster.
- We do not need to mimic the quickstart repo literally; we only want its good
  defaults: a thin entrypoint and a loadable package layout.

## Definitions best practices

`agents/definitions.py` should be the single place that assembles:

- assets
- jobs
- sensors
- schedules
- resources

Good patterns:

- `load_assets_from_modules(...)` for asset registration
- `Definitions(...)` as the top-level loadable object
- `Definitions.merge(...)` only when merging truly independent definition sets

Validation:

- Add a unit test that calls `defs.validate_loadable()`

Recommended test:

```python
from agents.definitions import defs


def test_definitions_loadable():
    defs.validate_loadable()
```

This should be treated as a required structural smoke test.

## Sensor best practices

Sensors should stay orchestration-only.

They may:

- poll for work
- decide whether to launch a run
- construct minimal run config
- emit `RunRequest` or `SkipReason`

They should not:

- perform heavy transformation
- perform expensive network fan-out
- contain business logic that belongs in assets or plain services

For this project:

1. Use `minimum_interval_seconds` deliberately.
2. Always prefer a `run_key` when launching work from queue items.
3. Add cursor state only when the queue volume or event volume requires it.
4. Keep sensor config-building small; extract helpers when the payload mapping
   starts growing.

Recommended direction for `work_queue_sensor`:

```python
yield RunRequest(
    run_key=str(item_id),
    run_config=run_config,
    tags={...},
)
```

If the same item can validly be retried with different upstream states, use a
more specific key, such as:

- item id + source page id
- item id + upstream updated timestamp

## Asset best practices

Assets should model the pipeline steps, not UI or transport concerns.

Good rules:

1. Keep each asset focused on one transformation boundary.
2. Prefer explicit inputs and outputs over hidden state.
3. Keep expensive LLM or OCR calls isolated so failures are easier to retry and
   inspect.
4. Share reusable helpers through plain modules, not through cross-calling
   assets.

The intended step shape here is now:

- acquisition
- prepared extraction inputs
- OCR / extraction
- analysis / normalization
- publish / synchronize

## Resource best practices

Resources should represent external systems, for example:

- API client
- scraper service
- storage backend

Resources should be:

- thin
- configured by environment
- easy to stub in tests

Resources should not accumulate data-shaping logic or orchestration decisions.
Push that logic into plain Python functions or service modules instead.

## Testing strategy

Split tests by layer:

1. Structure tests
   - `defs.validate_loadable()`
   - sensor/job registration smoke tests

2. Unit tests
   - `brain/`
   - `tools/`
   - shared helpers
   - pure data shaping

3. Asset and resource contract tests
   - asset config behavior
   - resource error handling
   - API payload contracts

4. External end-to-end tests
   - opt-in only
   - never the default fast feedback path

## Current repo guidance

The current `services/agents` structure is already close to the recommended
shape. The highest-value next improvements are:

1. keep `agents/definitions.py` thin and move pipeline contract wiring into
   shared helpers under `agents/defs/`
2. keep `work_queue_sensor` orchestration-only, with queue payload parsing and
   `RunRequest` construction delegated to helpers
3. keep assets thin by extracting normalized context dataclasses and pure helper
   functions for payload shaping, retries, and metadata building
4. keep business logic moving away from Dagster wrappers, not toward them

Patterns now preferred in this repo:

- normalized context dataclasses such as source-page or publish-origin contexts
- helper functions that return explicit value objects instead of loosely-shaped
  intermediate dicts
- shared pipeline constants and run-config builders in one place
- asset bodies that read like orchestration steps, not monolithic business logic

## Quick comparison with the official example

The cloned reference repo in `services/dagster-quickstart-reference/` is useful
for one thing: it shows the minimal loadable Dagster package shape.

What we should copy from it:

- small `definitions.py`
- simple package layout
- easy-to-find tests

What we should not copy blindly:

- its minimalism where our real service genuinely needs sensors, resources, and
  LLM/OCR pipeline stages

## Decision rule

When refactoring `services/agents`, prefer the change that makes the code:

1. more loadable by Dagster
2. easier to test without Dagster
3. less coupled to transport details
4. more explicit about orchestration boundaries
