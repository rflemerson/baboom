# Docker and Compose

## Ownership

- `apps/api/Dockerfile`: Django API image
- `apps/web/Dockerfile`: public web image
- `services/agents/Dockerfile`: agents service image
- `docker-compose.yml`: VM1 web/API/database/queue/worker orchestration
- `docker-compose.agents.yml`: VM2 Dagster/agents orchestration

## Rules

- Keep app images focused on the app they run.
- Do not keep orphaned frontend build stages inside the API image.
- Keep reverse proxy config under `infra/`, not inside app folders.
- Use non-root users in runtime images when practical.

## Compose expectations

- Healthchecks for infra services matter.
- Mount only what each service really needs.
- Remove stale volumes and mounts when the architecture changes.
- Keep `POSTGRES_DATA_PATH` pointed at the existing database directory in
  production; changing it creates a fresh PostgreSQL data directory.
- Use `NGINX_CONF=./infra/nginx/default.conf` in production so Cloudflare can
  validate the origin certificate. `infra/nginx/local.conf` is HTTP-only.
- VM1 production should pull prebuilt `API_IMAGE` and `WEB_IMAGE` from GHCR,
  then run `docker compose up -d --no-build ...` on small hosts.
- VM2 agents should pull prebuilt `AGENTS_IMAGE` from GHCR and use
  `docker-compose.agents.yml`.
- Use clear service names in compose:
  - `web` for the public frontend
  - `api` for Django
  - `celery` for task execution
  - `celery-beat` for database-backed periodic task scheduling
  - `agents` for Dagster in `docker-compose.agents.yml`
