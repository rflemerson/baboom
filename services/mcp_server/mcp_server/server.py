"""MCP tools for the local extraction-review workflow."""

from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

from .tools.api import (
    catalog_candidates,
    catalog_choices,
    review_queue,
)
from .tools.drafts import load_draft
from .tools.drafts import update_draft as update_draft_file
from .tools.formatting import format_item_summary
from .tools.image_report import create_image_report as create_image_report_for_item
from .tools.pages import download_images as download_images_for_item
from .tools.pages import fetch_source_page as fetch_source_page_data
from .tools.preparation import build_prepared_context
from .tools.review import (
    act_on_current_item,
    apply_current_item_extraction,
    approve_current_item,
    checkout_item,
    report_current_item_error,
    resume_item,
)
from .tools.submission import (
    build_submission_preview as build_submission_preview_payload,
)
from .tools.submission import (
    submit_draft as submit_draft_file,
)
from .tools.validation import validate_product_draft
from .tools.workspace import get_current_item, item_dir, write_json

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

mcp = MCPServer("extraction-review")

mcp.tool()(review_queue)
mcp.tool()(catalog_candidates)
mcp.tool()(catalog_choices)
mcp.tool()(resume_item)
mcp.tool()(act_on_current_item)
mcp.tool()(approve_current_item)
mcp.tool()(apply_current_item_extraction)


@mcp.tool()
def checkout_scraped_item(item_id: int | None = None) -> str:
    """Checkout the next queued scraped item and set it as current."""
    item = checkout_item(item_id)
    if not item:
        return "No item is available in the queue."

    return format_item_summary(item)


@mcp.tool()
def prepare_current_item() -> dict:
    """Extract structured context and image URLs for the current item.

    Use the result to decide whether to fetch the source page or download images.
    """
    item = get_current_item()
    prepared = build_prepared_context(item)
    write_json(item_dir(int(item["id"])) / "prepared.json", prepared)
    return {"ok": True, "prepared": prepared}


@mcp.tool()
def fetch_source_page(url: str | None = None) -> dict:
    """Render the source page and save its structured data in the workspace.

    The result includes metadata, JSON-LD blocks, tables, text, and images.
    """
    return fetch_source_page_data(url)


@mcp.tool()
def download_images(urls: list[str]) -> dict:
    """Download selected product or nutrition-label images to the workspace."""
    return download_images_for_item(urls)


@mcp.tool()
def create_image_report() -> dict:
    """Analyze downloaded images with the configured vision model.

    Save the resulting report for the current item.
    """
    return create_image_report_for_item()


@mcp.tool()
def show_current_item() -> str:
    """Show the current checked out scraped item."""
    item = get_current_item()
    return format_item_summary(item)


@mcp.tool()
def update_draft(patch: dict) -> dict:
    """Update the local extraction draft for the current item."""
    return update_draft_file(patch)


@mcp.tool()
def show_draft() -> dict:
    """Show the current local extraction draft."""
    return load_draft()


@mcp.tool()
def validate_draft() -> dict:
    """Validate the current local extraction draft."""
    return validate_product_draft(load_draft())


@mcp.tool()
def build_submission_preview(image_report: str | None = None) -> dict:
    """Build the submitAgentExtraction payload without sending it."""
    return build_submission_preview_payload(image_report=image_report)


@mcp.tool()
def submit_draft(
    image_report: str | None = None,
    *,
    confirm: bool = False,
) -> dict:
    """Submit the current validated draft to review staging. Requires confirm=True."""
    return submit_draft_file(image_report=image_report, confirm=confirm)


@mcp.tool()
def report_item_error(message: str, *, is_fatal: bool = False) -> dict:
    """Report an error for the current checked out scraped item."""
    return report_current_item_error(message, is_fatal=is_fatal)


def main() -> None:
    """Start the MCP server over its configured transport."""
    mcp.run()


if __name__ == "__main__":
    main()
