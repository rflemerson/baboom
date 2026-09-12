"""Smoke tests for the public MCP tool registry."""

import pytest

from mcp_server import server


@pytest.mark.asyncio
async def test_mcp_registers_admin_and_local_tools() -> None:
    """Expose both admin API operations and local processing tools."""
    names = {tool.name for tool in await server.mcp.list_tools()}
    assert {
        "admin_login",
        "admin_registry",
        "admin_create",
        "admin_action",
        "parse_page",
        "download_images",
        "create_image_report",
    } <= names
