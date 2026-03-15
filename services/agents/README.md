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
- LLM key(s) used by your provider (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`)

Image selection tuning:

- `OCR_INCLUDE_ALL_TABLES`
- `OCR_MAX_TABLE_CANDIDATES`
- `OCR_MAX_IMAGES`
- `OCR_MAX_NUTRITION_IMAGES`
- `OCR_MAX_IMAGES_NO_NUTRITION`
- `OCR_CV_TABLE_THRESHOLD`
