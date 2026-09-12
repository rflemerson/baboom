"""Smoke tests for the public MCP tool registry."""

import pytest

from mcp_server import server


@pytest.mark.asyncio
async def test_mcp_registers_admin_and_local_tools() -> None:
    """Expose both admin API operations and local processing tools."""
    tools = await server.mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {
        "admin_registry",
        "admin_create",
        "admin_action",
        "parse_page",
        "download_images",
        "create_image_report",
        "browser_open_page",
        "browser_snapshot",
        "browser_network",
        "browser_evaluate",
        "browser_close",
    } <= names
    forbidden_tool = "admin_" + "login"
    assert forbidden_tool not in names
    by_name = {tool.name: tool for tool in tools}
    assert by_name["browser_snapshot"].annotations.read_only_hint is True
    assert by_name["browser_network"].annotations.read_only_hint is True
    assert by_name["browser_click"].annotations.read_only_hint is False
