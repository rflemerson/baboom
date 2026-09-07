"""Exercise the public MCP transport without a live API or model."""

import asyncio
import json
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcp_server.tools.drafts import load_draft
from mcp_server.tools.workspace import set_current_item


def test_stdio_initialization_draft_edit_and_approval_preview(workspace):
    set_current_item({"id": 7, "status": "processing"})

    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            env={
                "MCP_WORKSPACE_DIR": str(workspace),
                "BACKEND_GRAPHQL_URL": "http://127.0.0.1:1/graphql/",
                "BACKEND_API_KEY": "test-only",
            },
        )
        async with (
            stdio_client(parameters) as (read, write),
            ClientSession(read, write, read_timeout_seconds=15) as session,
        ):
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"review_queue", "resume_item", "approve_current_item"} <= names
            edited = await session.call_tool(
                "update_draft", {"patch": {"name": "Whey"}}
            )
            assert not edited.is_error
            preview = await session.call_tool(
                "approve_current_item", {"product_id": 42}
            )
            assert not preview.is_error
            content = json.loads(preview.content[0].text)
            assert content["confirmationRequired"]

    asyncio.run(asyncio.wait_for(exercise(), timeout=25))
    assert load_draft()["name"] == "Whey"
