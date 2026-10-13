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
    # A developer's owner DM channel must never reach a test.
    monkeypatch.delenv('SLACK_OWNER_DM_CHANNEL', raising=False)
    # A developer's Slack base must never redirect the recorded adapter tests.
    monkeypatch.delenv('SLACK_API_BASE', raising=False)


@pytest.fixture(autouse=True)
def unread_deploys(monkeypatch):
    # #586: no test spawns gh for deployments. A test of the deploy rows requests this fixture,
    # whose value is the real reader, and restores it.
    from wuwei import metrics
    real = metrics._deploys
    monkeypatch.setattr(metrics, '_deploys', lambda root, config, since: ({}, 'code host not read in tests', False))
    return real


@pytest.fixture(autouse=True)
def unchecked_ziran():
    # #896 P8: the adapter remembers a passed version check per process; each test fakes its own.
    from wuwei import registry
    registry.CHECKED.clear()


@pytest.fixture(autouse=True)
def isolated_process_table(monkeypatch):
    # #952: lifecycle tests must never inspect or signal the developer's processes.
    from adapters.host import local
    from fakes.host import process_table
    from wuwei import registry
    read, load = local.processes, registry.load
    def refuse(record, grace, root=None):
        raise AssertionError('test attempted to signal a real process')
    def isolated(kind, config):
        adapter = load(kind, config)
        if kind == 'host' and config['adapters']['host'] == 'local':
            adapter.processes = lambda orphans=False, pid=None, root=None: registry.Result(0, process_table())
            adapter.terminate_process = refuse
        return adapter
    monkeypatch.setattr(registry, 'load', isolated)
    return read
