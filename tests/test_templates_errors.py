"""Operator-facing templates and recovery cues."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def cli(workspace, *args, input=None):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'cli'), 'WUWEI_WORKSPACE': str(workspace),
           'WUWEI_NOW': '2026-09-29T09:00:00+02:00'}
    return subprocess.run([sys.executable, '-P', '-m', 'wuwei', *args], cwd=workspace,
                          input=input, text=True, capture_output=True, env=env, timeout=20)


@pytest.fixture
def workspace(tmp_path):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'memory/goals.md').write_text('# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n')
    (base / 'config.toml').write_text('')
    return tmp_path


def test_plan_template_can_be_proposed_from_stdin(workspace):
    template = cli(workspace, 'plan', 'template')
    assert template.returncode == 0, template.stderr
    result = cli(workspace, 'plan', 'propose', '-', input=template.stdout)
    assert result.returncode == 0, result.stderr


def test_rank_template_can_be_ranked_from_stdin(workspace):
    template = cli(workspace, 'rank', 'template')
    assert template.returncode == 0, template.stderr
    result = cli(workspace, 'rank', '-', input=template.stdout)
    assert result.returncode == 0, result.stderr


def test_rice_templates_use_configured_components(workspace):
    (workspace / '.wuwei/config.toml').write_text('[prioritisation]\nframework = "rice"\n')
    for command in ('plan', 'rank'):
        template = cli(workspace, command, 'template')
        assert template.returncode == 0, template.stderr
        for component in ('reach', 'impact', 'confidence', 'effort'):
            assert f'"{component}"' in template.stdout
        result = cli(workspace, command, 'propose', '-', input=template.stdout) if command == 'plan' else cli(workspace, 'rank', '-', input=template.stdout)
        assert result.returncode == 0, result.stderr


def test_decision_template_lints(workspace):
    from wuwei.decision import lint
    result = cli(workspace, 'decision', 'template')
    assert result.returncode == 0, result.stderr
    assert lint(result.stdout)[0] == 0


@pytest.mark.parametrize('case,cue', [
    ('flags', 'trust_surface'),
    ('stand_down', 'wuwei build next'),
    ('reinit', '--upgrade'),
    ('mapping', 'seat_policy'),
])
def test_actionable_refusals(workspace, case, cue):
    from wuwei import brief, plan, workspace as config_module
    if case == 'flags':
        data = {'goals': ['G-1'], 'cap': 1, 'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 1},
                'sweep': {'manual': 'measured'}, 'candidates': [{'id': 'X', 'goal': 'G-1',
                'evidence': 'test', 'scope': 'test', 'overlap': 'none', 'track': 'SLICE',
                'score': {'value': 1, 'time_criticality': 1, 'risk_reduction': 1, 'job_size': 1},
                'evidence_lines': {key: 'test' for key in ('value', 'time_criticality', 'risk_reduction', 'job_size')},
                'flags': {}}]}
        with pytest.raises(ValueError) as error:
            plan._proposal(data, (workspace / '.wuwei/memory/goals.md').read_text())
        message = str(error.value)
    elif case == 'stand_down':
        with pytest.raises(brief.Refused) as error:
            brief.gate_ready({'items': {'X': {'phase': 'implement'}}, 'seats': {}}, 'X')
        message = str(error.value)
    elif case == 'reinit':
        message = cli(workspace, 'init', '.').stderr
    else:
        with pytest.raises(config_module.ConfigError) as error:
            config_module._validate({'builder': []}, {'builder': {'runtime': (str, '')}},
                                    ('seat_policy',), '[seat_policy]')
        message = str(error.value)
    assert cue in message


def test_brief_lock_timeout_has_reason(workspace, monkeypatch):
    from wuwei import state
    monkeypatch.setattr(state.fcntl, 'flock', lambda *args: (_ for _ in ()).throw(BlockingIOError()))
    monkeypatch.setattr(state, '_monotonic', iter([0, 31]).__next__)
    monkeypatch.setattr(state, '_sleep', lambda _: None)
    with (workspace / '.wuwei/brief.lock').open('a') as lock:
        with pytest.raises(TimeoutError, match='brief.lock'):
            state.lock_ex(lock, 'brief.lock')


def test_gate_head_refusal_names_head_and_gates(workspace):
    from wuwei.guards.pr import _recorded_gates
    code, reason = _recorded_gates(workspace, 'a' * 40, {}, 'X')
    assert code == 1
    assert 'a' * 40 in reason
    for gate in ('arch', 'quality', 'security'):
        assert gate in reason


def test_dirty_gate_brief_names_paths(workspace, monkeypatch):
    from wuwei import brief, registry, state, workspace as paths
    from wuwei.registry import Result
    day = paths.day_dir(workspace)
    day.mkdir(parents=True)
    state._write_state(lambda data: data['items'].update({'X': {'phase': 'gate'}}), workspace, reserved=False)
    class Vcs:
        def status(self, *args, **kwargs):
            return Result(0, [{'path': 'src/dirty.py'}])
        def head(self, *args, **kwargs):
            return Result(0, {'sha': 'a' * 40})
        def merge_base(self, *args, **kwargs):
            return Result(0, {'sha': 'a' * 40})
        def branches(self, *args, **kwargs):
            return Result(0, [])
    monkeypatch.setattr(registry, 'load', lambda *_: Vcs())
    with pytest.raises(brief.Refused, match='src/dirty.py'):
        brief.write('sentinel-arch', 'X', 'gate', 'body', worktree='repo', root=workspace)
