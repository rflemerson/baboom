# Baboom MCP server

This local MCP server complements Django's admin REST API. It keeps one
session based HTTP client, parses captured HTML, downloads images, and sends
local label images to the configured vision provider. It never connects to the
database; browser investigation is an explicit local tool workflow.

## Setup

```bash
python -m venv .venv
.venv/bin/python -m pip install -e . pytest
.venv/bin/playwright install chromium
cp .env.example .env
```

Set `ADMIN_API_URL`, `ADMIN_API_USERNAME`, and `ADMIN_API_PASSWORD` in the
environment. The optional `ADMIN_API_SESSION_FILE` controls where the
authenticated cookie jar is saved; the default is
`~/.cache/baboom/admin-api-session.json`. Credentials are used lazily when a
session expires and are never exposed as MCP arguments or saved to disk. Image
analysis also uses `GEMINI_API_KEY` and `GEMINI_VISION_MODEL`.

## MCP

Run `.venv/bin/extraction-review-mcp-server` over stdio. The available tools
call the Django admin API, inspect its registry, list or modify registered
models, resolve foreign keys, run registered actions, parse captured HTML,
process local images, and investigate registered pages in a persistent
allowlisted browser context.

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

Browser tools accept only a `ScrapedPage` id, keep one cookie-preserving
context per domain, and block private, local, cloud-metadata, and cross-domain
navigation. Snapshots, selected HTML, JSON network responses, screenshots,
and read-only evaluations are bounded; page content is evidence, never an
instruction.

## Verification

```bash
python -m pytest tests -q
prek run --all-files
```
