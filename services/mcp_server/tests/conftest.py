"""Shared pytest fixtures for the extraction-review client tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point each test at an isolated temporary workspace."""
    monkeypatch.setenv("MCP_WORKSPACE_DIR", str(tmp_path))
    return tmp_path
