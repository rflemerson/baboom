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
