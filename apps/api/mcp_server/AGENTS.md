# MCP Server Guide

## Scope

- Serves the catalog to agents over MCP, at `/mcp/`.
- Tools come from `django-admin-mcp-api`, which forwards to the registered
  `ModelAdmin` classes through `django-admin-rest-api`. No tool is defined here.
- This app adds the two things that package does not: token authentication and
  the curation instructions.

## Layout

- `views.py` — the Bearer bridge. Discards session identity, verifies the
  token through `django-oauth-toolkit`, runs as the token's user.
- `rpc.py` — the JSON-RPC methods the upstream package does not implement:
  `skills/*` (draft SEP-2640), `resources/*` and `prompts/*`.
- `loader.py` — reads `skills/`, refusing any path that leaves a skill.
- `skills/<slug>/SKILL.md` — the canonical instructions, with `references/`
  beside them. One copy, served to every client.

## Rules

- No curation rule belongs in Python here. `rpc.py` transports and validates
  the files; the rules live in the markdown.
- A skill must not name model fields as fact. It tells the agent to call
  `admin.form_spec` and use that answer.
- Authorization is the `ModelAdmin` permission check. The token's single scope
  only decides whether the endpoint may be reached at all.
- The route accepts a token and never a cookie. Exempting it from CSRF is only
  correct because of that.
- `skills/*` follows a specification that is final in its own branch but not
  merged. Keep the adapter in `rpc.py` so the shape can change in one place.
