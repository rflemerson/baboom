---
description: Docker & Deployment Reference
alwaysApply: true
applyTo: "**"
---

# Docker Reference

- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Compose Specification](https://github.com/compose-spec/compose-spec/blob/master/spec.md)
- [Hadolint Rules](https://github.com/hadolint/hadolint)

## Overview
The project uses `python:3.14-slim` for the application and `docker compose` for local orchestration.

## Dockerfile Structure

### 1. Base Image
`FROM python:3.14-slim`
-   **Why**: Minimal size, official maintenance.
-   **Env Vars**:
    -   `PYTHONDONTWRITEBYTECODE=1` (Speed)
    -   `PYTHONUNBUFFERED=1` (Logs)

### 2. System Dependencies
Install only runtime requirements.
```dockerfile
RUN apt-get update && apt-get install -y \
    libpq-dev gcc curl gettext \
    && rm -rf /var/lib/apt/lists/*
```
-   **Rule**: Always clean up apt lists (`rm -rf ...`) in the same layer to save space.

### 3. Application Installation
We treat the app as a package.
```dockerfile
COPY . /app/
RUN pip install --no-cache-dir .
```
-   **Rule**: `COPY . .` should be near the end to maximize layer caching.
-   **Rule**: Use `--no-cache-dir` to keep image size down.

### 4. Static Files & Assets
```dockerfile
RUN python manage.py compilemessages --ignore=.venv || true
RUN python manage.py collectstatic --noinput
```
-   **Rule**: Build assets at build time, not runtime.

### 5. Runtime
-   **User**: (Recommended) Create and switch to a non-root user `appuser`.
-   **CMD**: Use `gunicorn` for production.

---

## Docker Compose

**File**: `docker-compose.yml`

### Core Principles
1.  **Specification**: Use modern Compose format (no top-level `version:` key).
2.  **Healthchecks**: Mandatory for infrastructure services (DB, Queue).
3.  **Startup Order**: Use `depends_on` with `condition: service_healthy`.

### Service Patterns

#### Web (Django)
```yaml
services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app  # Hot-reloading
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

#### Database (Postgres)
```yaml
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: baboom
      POSTGRES_USER: baboom
      POSTGRES_PASSWORD: password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U baboom"]
      interval: 5s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

#### Queue (RabbitMQ)
```yaml
  rabbitmq:
    image: rabbitmq:3-management
    healthcheck:
      test: rabbitmq-diagnostics -q ping
      interval: 30s
      timeout: 30s
      retries: 3
    ports:
      - "15672:15672" # Management UI
```

### Volumes & Networks
-   **Volumes**: Use named volumes for persistence (`postgres_data`).
-   **Networks**: Use default bridge network unless isolation is strictly required.

### Networking Helpers
-   `host.docker.internal`: Use this to access host services (e.g. Playwright browsers running independently) from within containers.

## Security Best Practices
1.  **Non-Root**: Run as non-root user in production.
2.  **Secrets**: Never `COPY` `.env` files. Use environment variables.
3.  **Slim**: Stick to `slim` or `alpine` variants.
4.  **Linting**: Use `hadolint` to verify Dockerfile quality.
