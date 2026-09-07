"""Local review operations shared by the MCP and command-line clients."""

from . import api
from .drafts import draft_path
from .image_report import image_report_path, save_image_report
from .workspace import get_current_item, item_dir, set_current_item, write_json


def resume_item(item_id: int) -> dict:
    """Reload server state and restore evidence without overwriting local edits."""
    snapshot = api.review_item(item_id)
    item = snapshot.get("reviewItem")
    if item is None:
        raise api.APIError("Item não encontrado.")
    set_current_item(item)
    extraction = snapshot.get("reviewExtraction")
    if extraction:
        write_json(item_dir(item_id) / "staged.json", extraction)
        if not draft_path().exists():
            write_json(draft_path(), extraction["extractedProduct"])
        if not image_report_path().exists():
            save_image_report(extraction["imageReport"])
    return snapshot


def checkout_item(item_id: int | None = None) -> dict | None:
    """Reserve queued work and save its local context."""
    item = api.checkout_scraped_item(item_id)
    if item:
        set_current_item(item)
    return item


def act_on_current_item(action: str) -> dict:
    """Heartbeat, release or ignore the current item and refresh local state."""
    item = api.review_action(action, int(get_current_item()["id"]))
    set_current_item(item)
    return item


def approve_current_item(
    product_id: int | None = None,
    create_product: dict | None = None,
    confirm: bool = False,
) -> dict:
    """Preview catalog changes; confirm only after human approval."""
    payload = {
        "itemId": int(get_current_item()["id"]),
        "productId": product_id,
        "createProduct": create_product,
    }
    if (product_id is None) == (create_product is None):
        raise ValueError("Informe product_id ou create_product, exclusivamente.")
    if not confirm:
        return {"ok": False, "preview": payload, "confirmationRequired": True}
    product = api.approve_scraped_item(payload)
    item = get_current_item()
    item["status"] = "linked"
    set_current_item(item)
    write_json(
        item_dir(int(item["id"])) / "approval.json",
        {"request": payload, "product": product},
    )
    return {"ok": True, "product": product}


def report_current_item_error(message: str, is_fatal: bool = False) -> dict:
    """Report failure and update local state only after server acceptance."""
    item = get_current_item()
    result = api.report_scraped_item_error(int(item["id"]), message, is_fatal)
    if result["ok"]:
        item["status"] = "review" if is_fatal else "error"
        set_current_item(item)
    return result
