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
