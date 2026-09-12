"""Tests for the review workflow command-line interface."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import Mock

from mcp_server import cli
from mcp_server.tools import api
from mcp_server.tools.workspace import set_current_item

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_queue_is_read_only_and_outputs_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ensure queue listing does not reserve items and emits JSON."""
    queue = Mock(return_value=[{"id": 7}])
    monkeypatch.setattr(api, "review_queue", queue)
    assert cli.main(["queue", "--search", "Whey"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"id": 7}]
    queue.assert_called_once_with("queued", "Whey", 20)


def test_approve_requires_flag_before_remote_write(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Require explicit confirmation before an approval mutation."""
    set_current_item({"id": 7})
    approve = Mock(return_value={"id": 42})
    monkeypatch.setattr(api, "approve_scraped_item", approve)
    assert cli.main(["approve", "--product-id", "42"]) == 0
    assert json.loads(capsys.readouterr().out)["confirmationRequired"]
    approve.assert_not_called()
    assert cli.main(["approve", "--product-id", "42", "--confirm"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    approve.assert_called_once()


def test_invalid_patch_file_returns_error_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a structured error when a patch file is not an object."""
    path = tmp_path / "bad.json"
    path.write_text("[]", encoding="utf-8")
    assert cli.main(["update-draft", str(path)]) == 1
    assert "JSON object" in json.loads(capsys.readouterr().err)["error"]


def test_server_failure_returns_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return a non-zero status and JSON when the backend is unavailable."""
    monkeypatch.setattr(api, "review_queue", Mock(side_effect=api.APIError("Offline")))
    assert cli.main(["queue"]) == 1
    assert json.loads(capsys.readouterr().err) == {"ok": False, "error": "Offline"}
