# Agents Service (Isolated Dependencies)

This folder defines an isolated Python project for the `agents` service, intended to run on a separate server from the web app.

## Scope

- Dagster orchestration for `agents.definitions`
- Scraper + image selection + multimodal extraction pipeline
- API communication via `agents/client.py`

## Current Coupling

The current code still imports Django app models (`scrapers`, `core`) through `django.apps`.
Because of that, the runtime still needs project settings and repository code available in `PYTHONPATH`.

## Local Setup (isolated venv)

```bash
cd services/agents
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run from repository root so `agents/`, `baboom/`, `scrapers/`, and `core/` are importable:

```bash
cd /path/to/baboom
PYTHONPATH=. dagster dev -m agents.definitions
```

## Environment Variables

Minimum:

- `AGENTS_API_URL`
- `AGENTS_API_KEY`
- LLM key(s) used by `pydantic-ai` models (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`)

Selection behavior:

- `OCR_INCLUDE_ALL_TABLES`
- `OCR_MAX_TABLE_CANDIDATES`
- `OCR_MAX_IMAGES`
- `OCR_MAX_NUTRITION_IMAGES`
- `OCR_MAX_IMAGES_NO_NUTRITION`
- `OCR_CV_TABLE_THRESHOLD`

## Migration Target

To make `agents` fully standalone:

1. Remove direct `django.apps` model access from `agents/assets.py` and `agents/tools/scraper.py`.
2. Replace with API-based page/item lifecycle operations.
3. Keep this service project as the only dependency surface on the agents server.
