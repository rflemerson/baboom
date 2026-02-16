# Services Layout

This monorepo is deployed as two independent services:

1. `web`: Django app + scrapers + Celery workers/beat
2. `agents`: Dagster + LLM pipeline

Each service has its own dependency contract and environment template.

## Deploy Model

- `services/web`: runs with `python manage.py ...` and Celery commands.
- `services/agents`: runs with `PYTHONPATH=services/agents:. dagster dev -m agents.definitions` or Dagster daemon/processes.

## Shared Code

Both services use code from this repository. In production, deploy both from the same Git revision to avoid API/schema drift.
