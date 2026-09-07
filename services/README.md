# Local Review Tools

[`mcp_server`](mcp_server/README.md) provides the operator's MCP server and the
`baboom-review` CLI. Both share one GraphQL client and a local draft workspace.

The operator runs these tools locally; Django in `apps/api` owns queue state,
staging and catalog approval. No database credentials are needed by the client.
