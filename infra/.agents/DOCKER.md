# Docker and Compose

## Ownership

- `apps/api/Dockerfile`: Django API image
- `apps/web/Dockerfile`: public web image
- `services/agents/Dockerfile`: agents service image
- `docker-compose.yml`: local or deploy-style orchestration

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
- The current deployment model is one stack for `web`, `api`, and `agents` on the same host.
- Use clear service names in compose:
  - `web` for the public frontend
  - `api` for Django
  - `agents` for Dagster
