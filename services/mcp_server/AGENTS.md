# MCP Server Agent Instructions

This service exposes local MCP tools for extraction review.

## Rules

- Do not access the database directly.
- Use GraphQL API through the provided tools.
- Work with local drafts before submitting.
- Never call `submit_draft(confirm=True)` unless the user explicitly asks to send/submit.
- `checkout_scraped_item` changes a queued item to processing.
- `submit_draft` sends the extraction to review staging (requires `confirm=True`).
- Do not invent fields outside the extraction draft schema.
- If extraction is impossible, use `report_item_error`.
- MCP and CLI share `mcp_server/tools/api.py` and `tools/review.py`; do not add a
  second HTTP client. The CLI entrypoint is `baboom-review`.
- Use `review_queue` for discovery and `resume_item` to recover remote state.
  Resume restores staged drafts and image reports only when local files are absent.
- Use `act_on_current_item("heartbeat")` during processing, before the API's
  60-minute inactivity timeout. Release abandoned reservations explicitly.
- Approval is separate from staging: show `approve_current_item` without confirmation
  first, search catalog candidates, and send `confirm=True` only on explicit approval.
- New catalog products are unpublished. Nutrition, flavors and components remain
  available in extraction staging for detailed curation through Django admin.
- `schemas.py` validates nested local drafts; keep it aligned with the API DTOs.
- Test with `python -m pytest tests -q`; run `prek run --all-files` from this directory.
- Optional contract tests require API dev dependencies and `DJANGO_SETTINGS_MODULE`
  (see README); they exercise the real GraphQL view using a disposable test database.
