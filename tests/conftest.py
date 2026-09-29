"""Keep discovery of user MCP configuration inside the test sandbox."""

import pytest


@pytest.fixture(autouse=True)
def isolated_mcp_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp('mcp-home')
    monkeypatch.setenv('HOME', str(home))
