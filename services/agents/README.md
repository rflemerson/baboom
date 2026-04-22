# Agents Service (Dagster + LLM)

This folder defines the isolated dependency surface for the `agents` service, intended to run on a separate server from the Django web app.

## Scope

- Dagster orchestration for `agents.definitions`
- Image candidate selection + multimodal extraction pipeline
- API communication via GraphQL (`services/agents/agents/client.py`)

## Runtime Contract

- The service depends on API access to the web backend GraphQL endpoint.
- The service does **not** require Django runtime dependencies for execution.
- Keep both web and agents deployments on the same repository revision to avoid schema drift.
- Dagster loads jobs/assets only by default. Queue polling sensors are not
  registered, so processing starts only from a manual Dagster run.

## Local Setup (isolated venv)

```bash
cd services/agents
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a local env file from the example:

```bash
cp services/agents/.env.example services/agents/.env
```

The service reads variables from the process environment. For local runs, load
the file before starting Dagster:

```bash
set -a
source services/agents/.env
set +a
```

Run from repository root so `services/agents/agents` is importable:

```bash
cd /path/to/baboom
PYTHONPATH=services/agents:. dagster dev -m agents.definitions
```

## Production Runtime

Production runs Dagster as two long-lived services instead of `dagster dev`:

- `dagster-webserver`
  serves the UI on `127.0.0.1:3000`.
- `dagster-daemon`
  owns daemon responsibilities such as run queue, schedules, and sensors.

The production compose file is:

```bash
docker compose -f docker-compose.agents.yml up -d --no-build dagster-webserver dagster-daemon
```

Dagster state is persisted under `DAGSTER_STORAGE_PATH`, defaulting to:

```bash
/opt/baboom/dagster
```

This path uses the VM disk. It does not create a new OCI Block Volume.

The UI is intentionally bound to localhost on the VM. Access it with an SSH
tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 ubuntu@<agents-vm-ip>
```

Then open:

```text
http://localhost:3000
```

Queue sensors are still not registered by default, so production remains
manual-only unless `agents/definitions.py` explicitly adds sensors.

## Container Build

The service owns its container definition at `services/agents/Dockerfile`.

Build from repository root:

```bash
docker build -f services/agents/Dockerfile -t baboom-agents .
```

## Environment Variables

Minimum:

- `AGENTS_API_URL`
- `AGENTS_API_KEY`
- `IMAGE_REPORT_MODEL`
- `STRUCTURED_EXTRACTION_MODEL`
- LLM key(s) used by your provider (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`)

Recommended split:

- `IMAGE_REPORT_MODEL`
  multimodal model for `JSON + images -> ordered image report`
- `STRUCTURED_EXTRACTION_MODEL`
  cheaper text model for `image report + JSON context -> structured payload`

Deterministic image filtering:

- `AGENTS_IMAGE_FILTER_ENABLED`
  enable or disable URL-level filtering before the multimodal call
- `AGENTS_IMAGE_FILTER_STRIP_QUERY_FOR_DEDUPE`
  treat querystring-only URL variants as the same image
- `AGENTS_IMAGE_FILTER_MAX_IMAGES`
  cap the number of images kept after filtering; `0` means no cap
- `AGENTS_IMAGE_FILTER_EXCLUDE_KEYWORDS`
  comma-separated lowercase URL keywords to drop, useful for decorative assets
  such as logos, placeholders, sprites, swatches, badges, or store-specific
  branding frames

Dagster production:

- `DAGSTER_STORAGE_PATH`
  host path mounted as `DAGSTER_HOME` for persistent Dagster SQLite storage,
  artifacts, and compute logs

Observability:

- `AGENTS_SENTRY_DSN`
  Sentry DSN for the agents service
- `AGENTS_SENTRY_ENVIRONMENT`
  Sentry environment name, normally `production`
- `AGENTS_SENTRY_TRACES_SAMPLE_RATE`
  Sentry performance sample rate; `0.0` disables tracing but keeps errors
- `AGENTS_SENTRY_SEND_DEFAULT_PII`
  whether Sentry may send default PII

## GitHub Actions Deploy

Agents deploy is handled by `.github/workflows/deploy-agents.yml` and runs
against the `agents-production` GitHub environment.

Environment secrets:

- `AGENTS_SSH_KEY`
- `AGENTS_API_KEY`
- `GEMINI_API_KEY`
- `AGENTS_SENTRY_DSN`
- `GHCR_USER`
- `GHCR_TOKEN`

Environment variables:

- `AGENTS_HOST`
- `AGENTS_USER`
- `REGISTRY`
- `IMAGE_OWNER`
- `AGENTS_API_URL`
- `IMAGE_REPORT_MODEL`
- `STRUCTURED_EXTRACTION_MODEL`
- `AGENTS_HTTP_RETRIES`
- `AGENTS_HTTP_RETRY_BACKOFF`
- `AGENTS_IMAGE_FILTER_ENABLED`
- `AGENTS_IMAGE_FILTER_STRIP_QUERY_FOR_DEDUPE`
- `AGENTS_IMAGE_FILTER_MAX_IMAGES`
- `AGENTS_IMAGE_FILTER_EXCLUDE_KEYWORDS`
- `DAGSTER_STORAGE_PATH`
- `AGENTS_SENTRY_ENVIRONMENT`
- `AGENTS_SENTRY_TRACES_SAMPLE_RATE`
- `AGENTS_SENTRY_SEND_DEFAULT_PII`
