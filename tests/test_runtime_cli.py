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


def test_runtime_dispatch_uses_approved_role_policy(tmp_path, monkeypatch, capsys):
    from wuwei import state
    from wuwei.commands import runtime
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\nruntime="claude"\n')
    state._write_state(lambda data: data.update(seat_policy={
        'sentinel-arch': {'runtime': 'codex', 'model': 'test'}}), tmp_path, reserved=False)
    selected = []
    adapter = SimpleNamespace(dispatch=lambda *args, **kwargs:
                              registry.Result(0, {'id': 'one'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config:
                        selected.append(config['adapters']['runtime']) or adapter)
    assert runtime.run(SimpleNamespace(action='dispatch', role='sentinel-arch',
                                       brief='brief.md', worktree='tree', write=False), root=tmp_path) == 0
    assert selected == ['codex']
    job = json.loads(capsys.readouterr().out)
    assert job['runtime'] == 'codex'
    adapter.status = lambda job, *, root=None: registry.Result(0, {'status': 'completed'})
    assert runtime.run(SimpleNamespace(action='status', job=json.dumps(job)), root=tmp_path) == 0
    assert selected == ['codex', 'codex']


def test_runtime_dispatch_maps_gate_role_names(tmp_path, monkeypatch, capsys):
    from wuwei import state
    from wuwei.commands import runtime
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[adapters]\nruntime="claude"\n')
    state._write_state(lambda data: data.update(seat_policy={
        'sentinel-arch': {'runtime': 'codex', 'model': 'test'}}), tmp_path, reserved=False)
    seen = []
    adapter = SimpleNamespace(dispatch=lambda role, *args, **kwargs:
                              seen.append(role) or registry.Result(0, {'id': 'one'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config:
                        seen.append(config['adapters']['runtime']) or adapter)
    assert runtime.run(SimpleNamespace(action='dispatch', role='arch', brief='brief.md',
                                       worktree='tree', write=False), root=tmp_path) == 0
    assert seen == ['codex', 'sentinel-arch']
