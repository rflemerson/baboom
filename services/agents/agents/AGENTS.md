# Agents Module Guide (Dagster)

This file records official Dagster guidance applied to the `agents` module.
Goal: keep the pipeline simple, decoupled from Django, and scalable.

## Current Scope

- Dagster entrypoint: `agents/definitions.py`
- Dagster modules: `agents/defs/assets/*`, `agents/defs/sensors/*`, `agents/defs/resources/*`
- Domain logic modules: `agents/brain/`, `agents/tools/`, `agents/schemas/`

## Findings From Official Dagster Docs

1. A Dagster project should expose a single `Definitions` object per code location.
2. For a single project, organize code into modules/packages and avoid a monolithic file.
3. For multiple teams/projects/dependency sets, use multiple code locations via `workspace.yaml`.
4. `@dagster.definitions` is the recommended approach for lazy-loading definitions.
5. `Definitions` should centralize assets, jobs, sensors, schedules, and resources.

## Implemented Structure for `agents`

```text
agents/
  definitions.py                # code location entrypoint
  defs/
    assets/
      ingestion.py
      ocr.py
      analysis.py
      publish.py
    sensors/
      work_queue.py
    jobs/
      process_item.py
    resources/
      api_client.py
      scraper_service.py
      storage.py
  brain/
  tools/
  schemas/
  tests/
```

Notes:
- `defs/` should contain only Dagster-facing objects.
- `brain/`, `tools/`, and `schemas/` should stay Dagster-agnostic when possible.

## Practical Rules for This Repo

1. Keep `agents/definitions.py` as the single entrypoint.
2. Keep business logic out of sensors; sensors only fetch work and trigger run config.
3. Keep assets small and step-focused (ingestion -> cv/ocr -> structuring -> publish).
4. Keep resources stateless; configure by env and inject via `Definitions`.
5. Split testing by layer:
   - unit tests for pure logic (`brain`, `tools`, helpers),
   - contract tests for assets/resources,
   - opt-in external e2e tests (not default).

## Migration Status

1. `agents/assets.py` logic was extracted into `agents/defs/assets/*.py`.
2. Sensor logic was extracted into `agents/defs/sensors/work_queue.py`.
3. Resources were extracted into `agents/defs/resources/*.py`.
4. `agents/definitions.py` now wires Dagster directly from `agents/defs/*`.
5. Legacy compatibility facades were removed after import migration.

## Official References

- https://docs.dagster.io/guides/build/projects/dagster-project-file-reference
- https://docs.dagster.io/guides/build/projects/structuring-your-dagster-project
- https://docs.dagster.io/guides/build/projects/managing-multiple-projects-and-teams
- https://docs.dagster.io/guides/build/projects/workspaces
- https://docs.dagster.io/api/dagster/definitions
