@/infra/.agents/DOCKER.md
@/infra/.agents/NIX.md
@/infra/.agents/NGINX.md

---

# Infra Guide

## Scope

- This directory contains infrastructure and deployment configuration.
- Keep application code out of `infra/`.
- Keep deploy-only configuration, reverse proxy config, and environment orchestration here.
- The VM1 production stack is `web`, `api`, `nginx`, `db`, `redis`, `celery`,
  and `celery-beat`.
- Dagster/agents is isolated in `docker-compose.agents.yml` for VM2.
- Agents production deploy logic lives in `infra/deploy/agents.sh` and uses
  `dagster-webserver` plus one `dagster-daemon`.
- Agents production persists Dagster state on the VM disk under
  `DAGSTER_STORAGE_PATH`, defaulting to `/opt/baboom/dagster`; do not create OCI
  block volumes for this unless explicitly requested.
- Production deploy logic lives in `infra/deploy/`; keep GitHub Actions YAML thin
  and put orchestration, health waits, and diagnostics in versioned shell scripts.
- The deploy uses immutable GHCR image tags based on the full Git commit SHA.
