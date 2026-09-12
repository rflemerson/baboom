"""MCP tools that complement Django's admin REST API."""

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from .tools.admin_api import AdminAPIClient
from .tools.image_report import create_image_report as generate_image_report
from .tools.images import download_images as download_images_to_workspace
from .tools.page_data import parse_raw_html

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

mcp = MCPServer("baboom-admin")


@mcp.tool()
def admin_login(username: str, password: str) -> dict[str, Any]:
    """Authenticate a Django admin user and persist its session."""
    return AdminAPIClient().login(username, password)


@mcp.tool()
def admin_registry() -> dict[str, Any]:
    """Return the models visible to the authenticated admin user."""
    return AdminAPIClient().registry()


@mcp.tool()
def admin_list(
    app_label: str,
    model_name: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List rows through a registered Django ModelAdmin."""
    return AdminAPIClient().list(app_label, model_name, params=params)


@mcp.tool()
def admin_get(
    app_label: str,
    model_name: str,
    pk: int | str,
) -> dict[str, Any]:
    """Retrieve one row through a registered Django ModelAdmin."""
    return AdminAPIClient().retrieve(app_label, model_name, pk)


@mcp.tool()
def admin_create(
    app_label: str,
    model_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a row; Django's ModelForm is the validation authority."""
    return AdminAPIClient().create(app_label, model_name, payload)


@mcp.tool()
def admin_update(
    app_label: str,
    model_name: str,
    pk: int | str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Patch a row; Django's ModelForm is the validation authority."""
    return AdminAPIClient().update(app_label, model_name, pk, payload)


@mcp.tool()
def admin_autocomplete(
    app_label: str,
    model_name: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a foreign-key choice through Django admin autocomplete."""
    return AdminAPIClient().autocomplete(
        app_label,
        model_name,
        params=params,
    )


@mcp.tool()
def admin_action(
    app_label: str,
    model_name: str,
    action_name: str,
    pks: list[int | str],
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Run a registered Django ModelAdmin action."""
    return AdminAPIClient().action(
        app_label,
        model_name,
        action_name,
        pks,
        confirmed=confirmed,
    )


@mcp.tool()
def parse_page(raw_html: str, base_url: str | None = None) -> dict[str, object]:
    """Derive tables, visible text, and image references from captured HTML."""
    return parse_raw_html(raw_html, base_url=base_url)


@mcp.tool()
def download_images(urls: list[str], workspace: str) -> dict[str, object]:
    """Download selected product or label images to a local directory."""
    return download_images_to_workspace(urls, workspace)


@mcp.tool()
def create_image_report(workspace: str) -> dict[str, object]:
    """Analyze local label images with the configured vision provider."""
    return generate_image_report(workspace)


def main() -> None:
    """Start the MCP server over stdio."""
    mcp.run("stdio")


if __name__ == "__main__":
    main()
