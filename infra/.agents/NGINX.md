# Nginx

## Direction

- Keep Nginx configuration under `infra/nginx/`.
- Treat Nginx as infrastructure, not as part of the Django app codebase.

## Rules

- Proxy application traffic to the app container; do not embed app logic in Nginx config.
- Remove stale locations and volumes when backend/frontend responsibilities change.
- Keep TLS, proxy headers, and media routing explicit.
