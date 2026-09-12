"""Exercise the public MCP tool registry without a live API or model."""

import pytest

from mcp_server import server
from mcp_server.tools.drafts import load_draft
from mcp_server.tools.workspace import set_current_item


@pytest.mark.asyncio
async def test_mcp_tool_registration_draft_edit_and_approval_preview() -> None:
    """Exercise tool registration, draft editing, and approval preview in process."""
    set_current_item({"id": 7, "status": "processing"})
    names = {tool.name for tool in await server.mcp.list_tools()}
    assert {"review_queue", "resume_item", "approve_current_item"} <= names
    server.update_draft({"name": "Whey"})
    preview = server.approve_current_item(product_id=42)
    assert preview["confirmationRequired"]
    assert load_draft()["name"] == "Whey"
