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
- Product review runs from an operator workstation against the authenticated
  Django GraphQL API; only the API and public web have deployment images.
- Production deploy logic lives in `infra/deploy/`; keep GitHub Actions YAML thin
  and put orchestration, health waits, and diagnostics in versioned shell scripts.
- The deploy uses immutable GHCR image tags based on the full Git commit SHA.
