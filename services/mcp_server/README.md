# Extraction Review MCP Server

Local Model Context Protocol (MCP) server for extraction review.

## Setup & Running

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   playwright install chromium
   ```

2. Copy `.env.example` to `.env` and configure it:

   ```bash
   cp .env.example .env
   ```

3. Run the MCP server via stdio:

   ```bash
   extraction-review-mcp-server
   ```

## Configuration in Gemini CLI

Gemini CLI reads `mcpServers` settings in `settings.json`. You can register this server as follows:

```json
{
  "mcpServers": {
    "extraction-review": {
      "command": "/home/rafael/Documents/baboom/services/mcp_server/.venv/bin/extraction-review-mcp-server",
      "env": {
        "BACKEND_GRAPHQL_URL": "http://localhost:8000/graphql/",
        "BACKEND_API_KEY": "change-me",
        "MCP_WORKSPACE_DIR": "/home/rafael/Documents/baboom/services/mcp_server/workspace"
      }
    }
  }
}
```

> [!NOTE]
> Vision credentials and provider choices (`VISION_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_VISION_MODEL`) are loaded automatically from the `.env` file located in the `services/mcp_server` directory.
