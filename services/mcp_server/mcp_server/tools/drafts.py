"""Local JSON draft persistence for the extraction-review workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .validation import ALLOWED_PRODUCT_FIELDS
from .workspace import get_current_item_id, item_dir, read_json, write_json

if TYPE_CHECKING:
    from pathlib import Path

EMPTY_PRODUCT_DRAFT = {
    "name": None,
    "brandName": None,
    "ean": None,
    "weightGrams": None,
    "packaging": None,
    "quantity": None,
    "description": None,
    "categoryHierarchy": [],
    "tagsHierarchy": [],
    "flavorNames": [],
    "variantName": None,
    "nutritionFacts": None,
    "children": [],
}


def draft_path() -> Path:
    """Return the draft path for the currently checked-out item."""
    item_id = get_current_item_id()
    if not item_id:
        message = "No current item."
        raise RuntimeError(message)
    return item_dir(item_id) / "draft.json"


def ensure_draft() -> dict[str, Any]:
    """Create an empty draft when needed and return the current draft."""
    path = draft_path()
    if not path.exists():
        write_json(path, dict(EMPTY_PRODUCT_DRAFT))
    return read_json(path)


def load_draft() -> dict[str, Any]:
    """Load the current item's draft from disk."""
    return ensure_draft()


def update_draft(patch: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist a partial update to the current draft."""
    unknown = set(patch.keys()) - ALLOWED_PRODUCT_FIELDS
    if unknown:
        message = f"Unknown fields in patch: {', '.join(sorted(unknown))}"
        raise ValueError(message)
    draft = ensure_draft()
    draft.update(patch)
    write_json(draft_path(), draft)
    return draft
