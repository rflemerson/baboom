# Local Product Review

The MCP server and `baboom-review` CLI share one authenticated GraphQL client
and a workspace of item snapshots, extraction drafts, images and reports.
Run them on the operator's workstation. The client never connects to the database.

## Setup

From `services/mcp_server`, with Python 3.14 or newer:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e . pytest
cp .env.example .env
```

Configure `BACKEND_GRAPHQL_URL`, `BACKEND_API_KEY` and an absolute
`MCP_WORKSPACE_DIR`. Keep the workspace outside version control.
The optional image-analysis tool also needs `GEMINI_API_KEY`; queue, drafts,
staging and approval do not require model credentials.
Install Chromium with `.venv/bin/playwright install chromium` only when using
the source-page rendering tool.

## MCP

Run `.venv/bin/extraction-review-mcp-server` over stdio, or configure an MCP client:

```json
{
  "mcpServers": {
    "extraction-review": {
      "command": "/absolute/path/to/services/mcp_server/.venv/bin/extraction-review-mcp-server",
      "env": {
        "BACKEND_GRAPHQL_URL": "http://localhost:8000/graphql/",
        "BACKEND_API_KEY": "your-api-key",
        "MCP_WORKSPACE_DIR": "/absolute/path/to/review-workspace"
      }
    }
  }
}
```

The bundled skill is `mcp_server/skills/product-extraction-review/SKILL.md`.
The SDK dependency uses MCP 2.x and its `MCPServer` interface.

## CLI

After activating the virtual environment:

```bash
baboom-review queue --search Whey
baboom-review checkout --item-id 42
baboom-review prepare
baboom-review update-draft draft-patch.json
baboom-review validate
baboom-review submit
baboom-review submit --confirm
baboom-review candidates --search Whey
baboom-review choices brands --search Growth
baboom-review approve --product-id 123
baboom-review approve --product-id 123 --confirm
```

`submit` and `approve` preview their payload by default. Use `--confirm` only
after the operator approves the corresponding operation. For a new product,
replace `--product-id` with `--create-product approved-product.json`, containing
fields such as `{"name":"Whey","brandId":1,"netMass":1000,"massUnit":"g"}`.
Masses are submitted with their unit; the API stores them canonically.

Use `resume 42` to reload a review without overwriting local draft/report edits.
Use `heartbeat` during processing, before the 60-minute inactivity timeout;
`release` returns processing work to the queue, and `ignore` discards it.
`show`, `draft`, and `report-error "reason"` expose the remaining workflow.
Pass `--env-file /path/to/.env` before the command to select configuration explicitly.
Commands emit JSON; failures return a nonzero exit code.

Staging accepts recursive nutrition and combo evidence, but never changes the
catalog. Approval links an offer or creates an unpublished product using explicit
basic metadata and materializes its staged nutrition, flavors and combo components
atomically. Publication remains in Django admin. Missing or conflicting evidence
returns errors without partial catalog writes. API keys are trusted operator access,
not per-item ownership.

For an already linked item, run `resume ITEM_ID`, then
`apply-extraction --product-id PRODUCT_ID` to preview, and repeat with `--confirm`
after explicit approval. This fills empty relations from the server's staged JSON;
it never publishes, relinks an offer or overwrites conflicting catalog data.

Drafts accept `nutritionFacts`/`flavorNames` for one label, or `nutritionProfiles`
with those fields per entry for multiple labels. Macros are grams, energy is kcal,
and sodium requires `sodiumUnit`. Micronutrients require explicit units. Each simple
product needs a positive package mass, serving size and at least one measured nutrient.
Combo `children` require quantity plus `productId` or complete product metadata;
they are not flavor variants. See the API domain guide for conflict/reference rules.

## Verification

```bash
python -m pytest tests -q
prek run --all-files
```

Optional API contract tests use the API's dev environment, a disposable test
database, and the real GraphQL view. From the repository root:

```bash
PYTHONPATH=apps/api:services/mcp_server DJANGO_SECRET_KEY=local-test-only DJANGO_ENV=development apps/api/.venv/bin/python -m pytest --ds=baboom.settings services/mcp_server/tests -q
```

No live API, store, or model calls are made by these tests.
