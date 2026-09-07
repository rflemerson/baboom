from unittest.mock import Mock

import pytest

from mcp_server.tools import api, review, submission
from mcp_server.tools.drafts import load_draft, update_draft
from mcp_server.tools.image_report import load_image_report, save_image_report
from mcp_server.tools.workspace import get_current_item, set_current_item


@pytest.fixture
def current():
    item = {"id": 7, "status": "processing", "sourcePageId": 3}
    set_current_item(item)
    return item


def test_resume_restores_staged_evidence_and_preserves_local_edits(monkeypatch):
    snapshot = {
        "reviewItem": {"id": 7, "status": "review"},
        "reviewExtraction": {
            "extractedProduct": {"name": "Staged"},
            "imageReport": "Evidence",
        },
    }
    monkeypatch.setattr(api, "review_item", lambda _: snapshot)
    review.resume_item(7)
    assert load_draft()["name"] == "Staged"
    assert load_image_report() == "Evidence"
    update_draft({"name": "Local correction"})
    save_image_report("Local evidence")
    review.resume_item(7)
    assert load_draft()["name"] == "Local correction"
    assert load_image_report() == "Local evidence"


@pytest.mark.usefixtures("current")
def test_approval_preview_never_writes_and_confirmation_updates_state(monkeypatch):
    approve = Mock(return_value={"id": 42})
    monkeypatch.setattr(api, "approve_scraped_item", approve)
    preview = review.approve_current_item(product_id=42)
    assert preview["confirmationRequired"]
    approve.assert_not_called()
    assert review.approve_current_item(product_id=42, confirm=True)["ok"]
    assert get_current_item()["status"] == "linked"
    approve.assert_called_once_with(
        {"itemId": 7, "productId": 42, "createProduct": None}
    )


@pytest.mark.usefixtures("current")
def test_failed_approval_preserves_local_state(monkeypatch):
    monkeypatch.setattr(
        api, "approve_scraped_item", Mock(side_effect=api.APIError("Conflict"))
    )
    with pytest.raises(api.APIError, match="Conflict"):
        review.approve_current_item(product_id=42, confirm=True)
    assert get_current_item()["status"] == "processing"


@pytest.mark.usefixtures("current")
def test_staging_requires_confirmation_and_reports_backend_errors(monkeypatch):
    send = Mock(
        return_value={
            "extraction": None,
            "errors": [{"field": "itemId", "message": "Invalid state"}],
        }
    )
    monkeypatch.setattr(submission, "submit_agent_extraction", send)
    assert not submission.submit_draft()["ok"]
    send.assert_not_called()
    assert not submission.submit_draft(confirm=True)["ok"]
    assert get_current_item()["status"] == "processing"
    send.return_value = {"extraction": {"id": 1}, "errors": None}
    assert submission.submit_draft(confirm=True)["ok"]
    assert get_current_item()["status"] == "review"


@pytest.mark.usefixtures("current")
def test_invalid_nested_draft_is_not_submitted(monkeypatch):
    send = Mock()
    monkeypatch.setattr(submission, "submit_agent_extraction", send)
    update_draft({"children": [{"quantity": True}]})
    assert not submission.submit_draft(confirm=True)["ok"]
    send.assert_not_called()


@pytest.mark.usefixtures("current")
def test_failed_checkout_does_not_replace_current_item(monkeypatch, current):
    monkeypatch.setattr(api, "checkout_scraped_item", lambda _: None)
    assert review.checkout_item(99) is None
    assert get_current_item() == current
