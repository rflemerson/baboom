from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .tools.api import checkout_scraped_item as api_checkout_scraped_item
from .tools.api import report_scraped_item_error
from .tools.drafts import load_draft
from .tools.drafts import update_draft as update_draft_file
from .tools.dynamic_crawler import fetch_page_data
from .tools.formatting import format_item_summary
from .tools.image_report import create_image_report as create_image_report_for_item
from .tools.images import download_images as download_images_to_workspace
from .tools.preparation import build_prepared_context
from .tools.submission import (
    build_submission_preview as build_submission_preview_payload,
)
from .tools.submission import (
    submit_draft as submit_draft_file,
)
from .tools.validation import validate_product_draft
from .tools.workspace import get_current_item, item_dir, set_current_item, write_json

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

mcp = FastMCP("extraction-review")


@mcp.tool()
def checkout_scraped_item() -> str:
    """Checkout the next queued scraped item and set it as current."""
    item = api_checkout_scraped_item()
    if not item:
        return "Nenhum item disponível na fila."

    set_current_item(item)
    return format_item_summary(item)


@mcp.tool()
def prepare_current_item() -> dict:
    """Extract the structured context of the current item: parsed API context,
    parsed structured data and the image URLs found in them. Decide from this
    output what else is needed (fetch_source_page, download_images).
    """
    item = get_current_item()
    prepared = build_prepared_context(item)
    write_json(item_dir(int(item["id"])) / "prepared.json", prepared)
    return {"ok": True, "prepared": prepared}


@mcp.tool()
def fetch_source_page(url: str | None = None) -> dict:
    """Render the item's source page in a headless browser (needed for sites that
    only load content client-side) and return structured page data: title, meta
    tags, JSON-LD blocks, tables and every referenced image with alt text and
    where it was referenced (JSON-LD, meta, img tag). Also saves page.html and
    page_data.json in the item's workspace.
    """
    item = get_current_item()
    target = url or item.get("sourcePageUrl") or item.get("productLink")
    if not target:
        return {"ok": False, "error": "Item não tem URL de origem."}

    fetched = fetch_page_data(target)
    item_path = item_dir(int(item["id"]))
    (item_path / "page.html").write_text(fetched.pop("html"), encoding="utf-8")
    write_json(item_path / "page_data.json", fetched)

    return {"ok": True, "url": target, "pageData": fetched}


@mcp.tool()
def download_images(urls: list[str]) -> dict:
    """Download the chosen image URLs into the current item's workspace.
    Pick the URLs that matter for extraction (product photos, nutrition label
    images) from prepare_current_item / fetch_source_page output.
    """
    manifest = download_images_to_workspace(urls)
    return {
        "ok": True,
        "downloaded": manifest.get("downloaded", []),
        "errors": manifest.get("errors", []),
    }


@mcp.tool()
def create_image_report() -> dict:
    """Analyze the downloaded images with the configured vision model and save
    the resulting report for the current item.
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
def submit_draft(image_report: str | None = None, confirm: bool = False) -> dict:
    """Submit the current validated draft to review staging. Requires confirm=True."""
    return submit_draft_file(image_report=image_report, confirm=confirm)


@mcp.tool()
def report_item_error(message: str, is_fatal: bool = False) -> dict:
    """Report an error for the current checked out scraped item."""
    item = get_current_item()
    return report_scraped_item_error(
        item_id=int(item["id"]),
        message=message,
        is_fatal=is_fatal,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
