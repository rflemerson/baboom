@/infra/.agents/DOCKER.md
@/infra/.agents/NIX.md
@/infra/.agents/NGINX.md

---

# Infra Guide

## Scope

- This directory contains infrastructure and deployment configuration.
- Keep application code out of `infra/`.
- Keep deploy-only configuration, reverse proxy config, and environment orchestration here.
- The VM1 production stack is `web`, `api`, `nginx`, `db`, `rabbitmq`, `celery`,
  and `celery-beat`.
- Dagster/agents is isolated in `docker-compose.agents.yml` for a later VM2.
