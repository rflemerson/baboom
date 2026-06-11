import pytest


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_WORKSPACE_DIR", str(tmp_path))
    return tmp_path
