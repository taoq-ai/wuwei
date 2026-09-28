"""Runtime CLI forwards through the selected adapter."""

import json
from types import SimpleNamespace

from wuwei import registry


def test_runtime_cli_dispatch_and_status(tmp_path, monkeypatch, capsys):
    from wuwei.commands import runtime
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')

    class Fake:
        def dispatch(self, role, brief_path, worktree, write, *, root=None):
            assert (role, brief_path, worktree, write) == ('builder', 'brief.md', 'tree', True)
            return registry.Result(0, {'id': 'one'})

        def status(self, job, *, root=None):
            assert job == {'id': 'one'}
            return registry.Result(0, {'status': 'completed'})

    monkeypatch.setattr(registry, 'load', lambda kind, config: Fake())
    assert runtime.run(SimpleNamespace(action='dispatch', role='builder', brief='brief.md',
                                       worktree='tree', write=True, job=None), root=tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {'id': 'one'}
    assert runtime.run(SimpleNamespace(action='status', job='{"id":"one"}'), root=tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {'status': 'completed'}
