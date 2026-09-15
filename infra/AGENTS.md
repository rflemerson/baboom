@/infra/.agents/DOCKER.md
@/infra/.agents/NIX.md
@/infra/.agents/NGINX.md

---

# Infra Guide

## Scope

- This directory contains infrastructure and deployment configuration.
- Keep application code out of `infra/`.
- Keep deploy-only configuration, reverse proxy config, and environment orchestration here.
- Production runs on two machines. The web machine (`docker-compose.yml` plus
  `docker-compose.web.yml`) runs `nginx`, `web`, `api` and `db`; the worker
  machine (`docker-compose.worker.yml`) runs `celery`, `celery-beat` and
  `redis`. The only link between them is celery reaching postgres on the web
  machine's private address, which the subnet admits from the worker alone.
- `DEPLOY_ROLE` (`web` or `worker`) selects what `infra/deploy/production.sh`
  starts. The web machine deploys first, because its API applies migrations.
- Product curation uses Django admin; scrapers continue collecting source pages
  and offers. Only the API and public web have deployment images.
- Production deploy logic lives in `infra/deploy/`; keep GitHub Actions YAML thin
  and put orchestration, health waits, and diagnostics in versioned shell scripts.
- The deploy uses immutable GHCR image tags based on the full Git commit SHA.
