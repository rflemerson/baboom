# MCP Server Agent Instructions

This service exposes local tools for catalog work that Django does not provide.

- Use the Django admin REST API through `mcp_server.tools.admin_api`.
- Keep one persisted HTTP session client; do not access the database directly.
- Send model payloads unchanged and let Django's `ModelForm` validate them.
- Discover available models from the admin registry instead of hardcoding them.
- Treat HTTP 403 as a permission result for the signed-in user, separate from
  network failures.
- Keep image downloads and vision analysis local. Pass their working directory
  explicitly to each function.
- Parse page evidence from Django's stored `raw_html`; this service does not
  launch a browser.
- Keep the MCP server runnable over stdio with `python -m pytest tests -q` as
  the local test command.
