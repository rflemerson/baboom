# Local Review Tools

[`mcp_server`](mcp_server/README.md) provides the operator's MCP server and its
Django admin API client. The service keeps only local image work and page
parsing that Django does not provide.

The operator runs these tools locally; Django in `apps/api` owns the catalog
and its permissions. No database credentials are needed by the client.
