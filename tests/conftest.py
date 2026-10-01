"""Keep discovery of user MCP configuration inside the test sandbox."""

import pytest


@pytest.fixture(autouse=True)
def isolated_mcp_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp('mcp-home')
    monkeypatch.setenv('HOME', str(home))
    # A developer's gh token must never reach the config check's scope read.
    monkeypatch.delenv('GH_TOKEN', raising=False)
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    # A developer's Claude Code session must never leak into claims or the env export.
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.delenv('CLAUDE_ENV_FILE', raising=False)
    # A developer's owner DM channel must never turn test inbox events into commands.
    monkeypatch.delenv('SLACK_OWNER_DM_CHANNEL', raising=False)
    # A developer's Slack base must never redirect the recorded adapter tests.
    monkeypatch.delenv('SLACK_API_BASE', raising=False)


@pytest.fixture(autouse=True)
def quiet_heartbeat(monkeypatch):
    # The watch tick runs the heartbeat through the real launcher; a test that drives it
    # requests this fixture, whose value is the real beat, and restores it.
    from wuwei import heartbeat
    real = heartbeat.beat
    monkeypatch.setattr(heartbeat, 'beat', lambda root: 0)
    return real
