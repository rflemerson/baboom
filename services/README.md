# Services Layout

This folder currently contains the isolated `agents` service deployment contract.

The Django API app + scrapers now run from `apps/api`.

## Deploy Model

- `services/agents`: runs with `PYTHONPATH=services/agents:. dagster dev -m agents.definitions` or Dagster daemon/processes.

## Shared Code

Both services use code from this repository. In production, deploy both from the same Git revision to avoid API/schema drift.
