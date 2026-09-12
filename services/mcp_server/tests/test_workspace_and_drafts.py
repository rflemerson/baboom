"""Tests for workspace snapshots and local product drafts."""

import pytest

from mcp_server.tools.drafts import EMPTY_PRODUCT_DRAFT, load_draft, update_draft
from mcp_server.tools.workspace import (
    get_current_item,
    get_current_item_id,
    set_current_item,
)

ITEM = {"id": "42", "name": "Whey", "storeSlug": "growth"}


def test_current_item_roundtrip() -> None:
    """Persist and reload the current item snapshot."""
    assert get_current_item_id() is None

    set_current_item(ITEM)

    expected_item_id = 42
    assert get_current_item_id() == expected_item_id
    assert get_current_item() == ITEM


def test_get_current_item_without_checkout() -> None:
    """Raise a clear error when no item has been checked out."""
    with pytest.raises(RuntimeError, match="No current item"):
        get_current_item()


def test_draft_lifecycle() -> None:
    """Create, update, and reload a local draft."""
    set_current_item(ITEM)

    assert load_draft() == EMPTY_PRODUCT_DRAFT

    draft = update_draft({"name": "Whey 1kg", "flavorNames": ["Chocolate"]})

    assert draft["name"] == "Whey 1kg"
    assert draft["flavorNames"] == ["Chocolate"]
    assert load_draft() == draft


def test_update_draft_rejects_unknown_fields() -> None:
    """Reject updates containing fields outside the draft schema."""
    set_current_item(ITEM)

    with pytest.raises(ValueError, match="Unknown fields"):
        update_draft({"foo": 1})
