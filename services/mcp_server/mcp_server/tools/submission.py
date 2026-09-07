from typing import Any

from .api import submit_agent_extraction
from .drafts import load_draft
from .image_report import load_image_report
from .validation import validate_product_draft
from .workspace import get_current_item, set_current_item


def build_submission_preview(image_report: str | None = None) -> dict[str, Any]:
    item = get_current_item()
    draft = load_draft()

    if image_report is None:
        image_report = load_image_report()

    return {
        "originScrapedItemId": int(item["id"]),
        "sourcePageId": item.get("sourcePageId"),
        "sourcePageUrl": item.get("sourcePageUrl"),
        "storeSlug": item.get("storeSlug"),
        "imageReport": image_report or "",
        "product": draft,
    }


def submit_draft(
    image_report: str | None = None, confirm: bool = False
) -> dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "errors": [
                "Confirmação explícita obrigatória. Chame com confirm=true apenas quando o usuário pedir para enviar.",
            ],
        }

    draft = load_draft()
    validation = validate_product_draft(draft)
    if not validation["ok"]:
        return {
            "ok": False,
            "errors": validation["errors"],
        }

    payload = build_submission_preview(image_report=image_report)
    result = submit_agent_extraction(payload)
    if result.get("errors") or not result.get("extraction"):
        return {
            "ok": False,
            "errors": result.get("errors") or ["Extração não retornada."],
        }
    item = get_current_item()
    item["status"] = "review"
    set_current_item(item)

    return {
        "ok": True,
        "result": result,
    }
