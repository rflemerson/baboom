# Baboom MCP server

This local MCP server complements Django's admin REST API. It keeps one
session based HTTP client, parses captured HTML, downloads images, and sends
local label images to the configured vision provider. It never connects to the
database and never renders pages itself.

## Setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e . pytest
cp .env.example .env
```

Set `ADMIN_API_URL` to the Django origin. The optional
`ADMIN_API_SESSION_FILE` controls where the authenticated cookie jar is saved;
the default is `~/.cache/baboom/admin-api-session.json`. Image analysis also
uses `GEMINI_API_KEY` and `GEMINI_VISION_MODEL`.

## MCP

Run `.venv/bin/extraction-review-mcp-server` over stdio. The available tools
authenticate and call the Django admin API, inspect its registry, list or
modify registered models, resolve foreign keys, run registered actions, parse
captured HTML, and process local images.

The admin API is the source of truth. Payloads are sent directly to Django's
`ModelForm`; the client does not duplicate validation or mass conversion. A
403 is reported as a permission error for the signed-in user, distinct from a
network failure.

## Local page parsing

`parse_page` receives the `raw_html` returned by Django and derives visible
text, HTML tables, and image references. Scripts, styles, templates, and
noscript elements are excluded from visible text. `download_images` and
`create_image_report` accept an explicit local directory, so no global item
state is required.

## Verification

```bash
python -m pytest tests -q
prek run --all-files
```
